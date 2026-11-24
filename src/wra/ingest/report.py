"""The data report: what is in the database, read back from the database itself.

It exists so a person can check the data before any score is built on it:
where each hub was placed, whether the sources agree on that, how complete the
station record is, which warning types are present and how long they last.
"""

import sqlite3
import statistics
from datetime import date, datetime
from pathlib import Path


def data_report(db_path: Path, raw_dir: Path) -> tuple[str, bool]:
    """Return the report text, and False if something in it needs a person's attention."""
    if not db_path.exists():
        return f"No database at {db_path}. Run `wra ingest` first.", False
    connection = sqlite3.connect(db_path)
    try:
        return _report(connection, raw_dir)
    finally:
        connection.close()


def _report(db: sqlite3.Connection, raw_dir: Path) -> tuple[str, bool]:
    meta = dict(db.execute("SELECT key, value FROM meta"))
    start, end = date.fromisoformat(meta["period_start"]), date.fromisoformat(meta["period_end"])
    days_expected = (end - start).days + 1
    fetched = db.execute("SELECT min(fetched_at), max(fetched_at) FROM fetch_log").fetchone()
    when = fetched[0] if fetched[0] == fetched[1] else f"{fetched[0]} to {fetched[1]}"
    out = [
        f"DATA REPORT   period {start} to {end}   fetched {when}",
        f"   Warnings requested by issue date {meta['warnings_issued_from']} up to (not including) "
        f"{meta['warnings_issued_before']}, UTC, so warnings that cross the period's edges are complete.",
        "   Scoring keeps only the hours inside the period, in each hub's time zone.",
        "",
    ]

    out += ["1. Where each hub is, and whether the sources agree on its county", ""]
    hubs = db.execute(
        "SELECT hub_id, station_name, lat, lon, county_name, state, county_fips, station_county_fips, "
        "warning_county_codes, warning_zone_codes, county_check FROM hubs ORDER BY rowid"
    ).fetchall()
    out += _table(
        ["hub", "station (NOAA)", "lat, lon", "county (FEMA)", "station says", "warnings say", "check", "zones"],
        [
            [h[0], h[1], f"{h[2]}, {h[3]}", f"{h[4]}, {h[5]} {h[6]}", h[7], h[8] or "-", h[10], h[9] or "-"]
            for h in hubs
        ],
    )
    differing = [h[0] for h in hubs if h[10] != "agree"]
    out += [
        "",
        f"County check (FEMA against the warning archive, both read from the map): "
        f"{len(hubs) - len(differing)} of {len(hubs)} hubs agree.",
    ]
    if differing:
        out += [f"NEEDS A LOOK: FEMA and the warning archive name different counties for {', '.join(differing)}."]
    relabelled = [h[0] for h in hubs if h[7] != h[6]]
    if relabelled:
        out += [
            f"Note: the station service labels {', '.join(relabelled)} with a different county than both maps give "
            "for the station's coordinates. The hub's county is the one the maps give."
        ]

    out += ["", "2. Rows per hub, and how complete the station record is", ""]
    rows = []
    for (hub_id,) in db.execute("SELECT hub_id FROM hubs ORDER BY rowid").fetchall():
        zone, polygon = (
            db.execute(
                "SELECT count(*) FROM warning_events WHERE hub_id = ? AND matched_by = ?", (hub_id, kind)
            ).fetchone()[0]
            for kind in ("zone", "polygon")
        )
        skipped = db.execute("SELECT count(*) FROM skipped_records WHERE hub_id = ?", (hub_id,)).fetchone()[0]
        days, snow_m, snow_t, rain_m = db.execute(
            "SELECT count(*), coalesce(sum(snow_flag = 'M'), 0), coalesce(sum(snow_flag = 'T'), 0), "
            "coalesce(sum(precip_flag = 'M'), 0) FROM station_daily WHERE hub_id = ?",
            (hub_id,),
        ).fetchone()
        absent = days_expected - days
        rows.append(
            [
                hub_id, zone, polygon, skipped, f"{days} of {days_expected}",
                f"{snow_m + absent} ({_pct(snow_m + absent, days_expected)})", snow_t,
                f"{rain_m + absent} ({_pct(rain_m + absent, days_expected)})",
            ]
        )  # fmt: skip
    out += _table(
        ["hub", "zone rows", "polygon rows", "skipped", "station days", "snow missing", "snow trace", "rain missing"],
        rows,
    )

    out += ["", "3. FEMA hurricane frequency per hub county (tropical storms included)", ""]
    release = db.execute("SELECT DISTINCT release FROM fema_nri").fetchall()
    figures = db.execute(
        "SELECT h.hub_id, h.county_name, f.value FROM hubs h JOIN fema_nri f USING (hub_id) "
        "WHERE f.field = 'HRCN_AFREQ' ORDER BY h.rowid"
    ).fetchall()
    out += _table(
        ["hub", "county", "events per year", "about one every"],
        [
            [hub, county, _num(freq, 4), f"{1 / freq:.0f} years" if freq else "-"]
            for hub, county, freq in figures
        ],
    )
    out += [
        "",
        f"   FEMA release: {', '.join(r[0] for r in release)}. A dash means FEMA gives the county no hurricane figure.",
        "   FEMA assigns 0.01 a year to land it considers reachable where no storm was recorded. Land with one",
        "   storm on record in 174 years gets about 0.006, so a county's average can fall below 0.01.",
    ]

    out += ["", "4. Warning types present (warnings only), and how long one row lasts", ""]
    out += [
        "   Rows are counted before overlapping warnings are merged. 'zone' means issued for the hub's",
        "   forecast zone or county; 'polygon' means the drawn area covered the hub itself.",
        "",
    ]
    spans: dict[tuple[str, str, str], list[tuple[str, float]]] = {}
    for kind, code, name, hub_id, issue, expire in db.execute(
        "SELECT matched_by, phenomena, name, hub_id, issue_utc, expire_utc FROM warning_events WHERE significance = 'W'"
    ):
        hours = (_time(expire) - _time(issue)).total_seconds() / 3600
        spans.setdefault((kind, code, name), []).append((hub_id, hours))
    out += _table(
        ["matched by", "code", "name", "hubs", "rows", "median hours", "longest hours", "total days"],
        [
            [
                kind, code, name, len({hub for hub, _ in found}), len(found),
                _num(statistics.median(h for _, h in found), 1), _num(max(h for _, h in found), 1),
                _num(sum(h for _, h in found) / 24, 1),
            ]
            for (kind, code, name), found in sorted(spans.items(), key=lambda item: (item[0][0], -len(item[1])))
        ],
    )  # fmt: skip

    out += ["", "5. Records left out", ""]
    skipped_rows = db.execute(
        "SELECT source, reason, count(*) FROM skipped_records GROUP BY 1, 2 ORDER BY 1, 2"
    ).fetchall()
    out += _table(["source", "reason", "records"], [list(r) for r in skipped_rows]) if skipped_rows else ["   none"]

    out += ["", "6. Raw responses kept on disk", ""]
    files = [p for p in raw_dir.rglob("*") if p.is_file()] if raw_dir.exists() else []
    total = sum(p.stat().st_size for p in files)
    out += [f"   {len(files)} files, {total / 1_000_000:.1f} MB under {raw_dir}"]
    return "\n".join(out), not differing


def _table(headers: list[str], rows: list[list]) -> list[str]:
    cells = [headers] + [[str(value) for value in row] for row in rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]
    lines = ["   " + "  ".join(value.ljust(width) for value, width in zip(row, widths)).rstrip() for row in cells]
    lines.insert(1, "   " + "  ".join("-" * width for width in widths))
    return lines


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%"


def _num(value: float | None, decimals: int) -> str:
    return "-" if value is None else f"{value:.{decimals}f}"


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text)
