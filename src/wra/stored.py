"""Read the database built by `wra ingest` into plain values, once per process.

The scoring core and the tools work on these values and never run SQL
themselves, so they can be tested on hand-built inputs.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from wra.ingest.iem import WarningEvent


@dataclass(frozen=True)
class HubRecord:
    hub_id: str
    city: str
    state: str
    region: str
    tz: str
    station_id: str
    station_name: str
    lat: float
    lon: float
    county_fips: str
    county_name: str


@dataclass(frozen=True)
class StationDay:
    day: date
    snow_in: float | None
    snow_flag: str  # '' measured, 'T' trace, 'M' missing
    precip_in: float | None
    precip_flag: str


@dataclass(frozen=True)
class StoredData:
    hubs: dict[str, HubRecord]  # in the order of config/hubs.toml
    warnings: dict[str, list[WarningEvent]]  # every type and level, as stored
    fema: dict[str, dict[str, float | None]]  # hub -> FEMA field -> value
    fema_release: str
    days: dict[str, list[StationDay]]
    period_start: date
    period_end: date
    data_as_of: str  # the day the newest stored response was fetched


class NoDatabase(RuntimeError):
    pass


def load_stored(db_path: Path) -> StoredData:
    if not db_path.exists():
        raise NoDatabase(f"no database at {db_path}; run `uv run wra ingest` first (offline, about a second)")
    db = sqlite3.connect(db_path)
    try:
        return _load(db)
    finally:
        db.close()


def _load(db: sqlite3.Connection) -> StoredData:
    hubs = {
        r[0]: HubRecord(*r)
        for r in db.execute(
            "SELECT hub_id, city, state, region, tz, station_id, station_name, lat, lon, county_fips, county_name "
            "FROM hubs ORDER BY rowid"
        )
    }
    warnings: dict[str, list[WarningEvent]] = {hub: [] for hub in hubs}
    for r in db.execute(
        "SELECT hub_id, matched_by, wfo, vtec_year, phenomena, significance, event_id, ugc, issue_utc, expire_utc, name "
        "FROM warning_events ORDER BY rowid"
    ):
        warnings[r[0]].append(WarningEvent(*r[1:8], _utc(r[8]), _utc(r[9]), r[10]))
    fema: dict[str, dict[str, float | None]] = {hub: {} for hub in hubs}
    for hub, field, value in db.execute("SELECT hub_id, field, value FROM fema_nri"):
        fema[hub][field] = value
    releases = sorted({r[0] for r in db.execute("SELECT DISTINCT release FROM fema_nri")})
    days: dict[str, list[StationDay]] = {hub: [] for hub in hubs}
    for r in db.execute(
        "SELECT hub_id, day, snow_in, snow_flag, precip_in, precip_flag FROM station_daily ORDER BY hub_id, day"
    ):
        days[r[0]].append(StationDay(date.fromisoformat(r[1]), *r[2:]))
    meta = dict(db.execute("SELECT key, value FROM meta"))
    fetched = db.execute("SELECT max(fetched_at) FROM fetch_log").fetchone()[0]
    return StoredData(
        hubs=hubs,
        warnings=warnings,
        fema=fema,
        fema_release=", ".join(releases),
        days=days,
        period_start=date.fromisoformat(meta["period_start"]),
        period_end=date.fromisoformat(meta["period_end"]),
        data_as_of=fetched[:10],
    )


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(text)
