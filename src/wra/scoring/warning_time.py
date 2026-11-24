"""Time under warning: pick a hazard's warnings, merge them into spells, sum the hours per local year.

Pure functions over plain values: no database, no network (docs/PLAN.md, section 5.2).

The rules, in the order they apply:
1. Warnings only (significance W), and only the hazard's type codes.
2. A zone code counts from a forecast-zone row (area code with Z as its third
   letter). A polygon code counts from a drawn-area row, which covered the hub
   itself; its county row (same office, year, type and event number) can only
   shorten it, never lengthen it (open point O12).
3. A record whose expiry is not after its issue time carries no time.
4. Within one hazard, overlapping and repeated warnings merge into one spell.
5. Each hour belongs to the calendar year it falls in, in the hub's time zone,
   and only hours inside the period count. Hours are real elapsed hours,
   measured in UTC, so a clock change does not add or remove one.
"""

from collections.abc import Iterable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from wra.ingest.iem import WarningEvent

Spell = tuple[datetime, datetime]  # start and end, UTC

_SAME_WARNING = ("wfo", "vtec_year", "phenomena", "significance", "event_id")


def counted_spells(rows: Iterable[WarningEvent], zone_codes: list[str], polygon_codes: list[str]) -> list[Spell]:
    """The spells one hazard counts, before merging. Rules 1 to 3."""
    warnings = [r for r in rows if r.significance == "W" and r.expire_utc > r.issue_utc]
    county_end: dict[tuple, datetime] = {}
    for r in warnings:
        if r.matched_by == "zone" and _is_county(r.ugc) and r.phenomena in polygon_codes:
            key = _key(r)
            county_end[key] = max(county_end.get(key, r.expire_utc), r.expire_utc)

    spells: list[Spell] = []
    for r in warnings:
        if r.matched_by == "zone" and r.phenomena in zone_codes and _is_forecast_zone(r.ugc):
            spells.append((r.issue_utc, r.expire_utc))
        elif r.matched_by == "polygon" and r.phenomena in polygon_codes:
            end = min(r.expire_utc, county_end.get(_key(r), r.expire_utc))
            if end > r.issue_utc:
                spells.append((r.issue_utc, end))
    return spells


def merge_spells(spells: Iterable[Spell]) -> list[Spell]:
    """Merge overlapping, touching and repeated spells, so no hour is counted twice. Rule 4."""
    merged: list[Spell] = []
    for start, end in sorted(spells):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def hours_by_year(merged: list[Spell], tz: str, first_year: int, last_year: int) -> dict[int, float]:
    """Hours under warning in each local calendar year of the period. Rule 5.

    `merged` must already be merged; every year of the period is present, zero if quiet.
    """
    zone = ZoneInfo(tz)
    hours: dict[int, float] = {}
    for year in range(first_year, last_year + 1):
        year_start = datetime(year, 1, 1, tzinfo=zone).astimezone(UTC)
        year_end = datetime(year + 1, 1, 1, tzinfo=zone).astimezone(UTC)
        seconds = 0.0
        for start, end in merged:
            overlap = (min(end, year_end) - max(start, year_start)).total_seconds()
            if overlap > 0:
                seconds += overlap
        hours[year] = seconds / 3600
    return hours


def days_by_year(
    rows: Iterable[WarningEvent],
    zone_codes: list[str],
    polygon_codes: list[str],
    *,
    tz: str,
    first_year: int,
    last_year: int,
) -> dict[int, float]:
    """Days under warning (hours divided by 24) for one hazard at one hub, per local year."""
    merged = merge_spells(counted_spells(rows, zone_codes, polygon_codes))
    return {year: h / 24 for year, h in hours_by_year(merged, tz, first_year, last_year).items()}


def _key(r: WarningEvent) -> tuple:
    return tuple(getattr(r, field) for field in _SAME_WARNING)


def _is_forecast_zone(ugc: str | None) -> bool:
    return ugc is not None and len(ugc) == 6 and ugc[2] == "Z"


def _is_county(ugc: str | None) -> bool:
    return ugc is not None and len(ugc) == 6 and ugc[2] == "C"
