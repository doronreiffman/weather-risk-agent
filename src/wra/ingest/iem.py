"""Iowa Environmental Mesonet warning archive: past Weather Service warnings for a point.

Two services, both used (docs/PLAN.md, section 5.2):

- by zone:    every warning issued for the forecast zone or county that
              contains the point. Winter and coastal warnings are issued this way.
- by polygon: every warning whose drawn area covered the point itself. Flash
              flood, severe thunderstorm and tornado warnings are drawn this way.
              Each row is the warning as first drawn, with its first planned
              end. If the warning was later cancelled early or extended for the
              hub's county, that shows only in the county's zone row for the same
              event (measured 2026-11-24: 104 of 920 severe thunderstorm rows end
              later here than in the county row). The scoring code reconciles them.

All rows are kept, whatever their type. Which types count toward the score is
decided by the scoring config, not here.

Both services select by issue date: `sdate` inclusive, `edate` exclusive, UTC.
See WARNINGS_ISSUED_FROM in this package for the range we ask for and why.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from wra.ingest.errors import SourceError
from wra.ingest.points import checked_point

ZONE_URL = "https://mesonet.agron.iastate.edu/json/vtec_events_bypoint.py"
POLYGON_URL = "https://mesonet.agron.iastate.edu/json/sbw_by_point.py"

_VTEC_YEAR = re.compile(r"[?&]year=(\d{4})(?:&|$)")


@dataclass(frozen=True)
class WarningEvent:
    """One spell of one warning at the hub. The same warning can have several."""

    matched_by: str  # "zone" or "polygon"
    wfo: str  # the issuing forecast office, for example "FWD"
    vtec_year: int  # the year the office numbered this event in
    phenomena: str  # two-letter type code, for example "WS" for winter storm
    significance: str  # "W" warning, "A" watch, "Y" advisory
    event_id: int
    ugc: str | None  # the county or zone code it was issued for; None for a polygon match
    issue_utc: datetime
    expire_utc: datetime
    name: str


@dataclass(frozen=True)
class SkippedRecord:
    reason: str
    record: dict


@dataclass(frozen=True)
class ParsedEvents:
    events: list[WarningEvent]
    skipped: list[SkippedRecord]


def request_params(lat: float, lon: float, start: date, end: date) -> dict[str, str]:
    """Query parameters for either service. Refuses a missing or implausible point.

    Returns warnings issued on or after `start` and before `end` (UTC dates).
    """
    lat, lon = checked_point(lat, lon)
    return {
        "lat": repr(lat),
        "lon": repr(lon),
        "sdate": start.isoformat(),
        "edate": end.isoformat(),
    }


def parse_zone_response(payload: dict) -> ParsedEvents:
    return _parse_rows(_rows(payload, "events"), matched_by="zone")


def parse_polygon_response(payload: dict, lat: float, lon: float) -> ParsedEvents:
    """Parse a by-polygon response, after checking it answers for the point we asked about."""
    echoed = (payload.get("lat"), payload.get("lon"))
    if echoed != (lat, lon):
        raise SourceError(f"polygon response is for a different point: asked {(lat, lon)}, got {echoed}")
    return _parse_rows(_rows(payload, "sbws"), matched_by="polygon")


def area_codes(events: list[WarningEvent]) -> tuple[list[str], list[str]]:
    """The county codes and the forecast-zone codes that the events were issued for.

    A code such as TXC113 is a county (third letter C); TXZ119 is a forecast zone.
    """
    codes = {e.ugc for e in events if e.ugc}
    unknown = sorted(c for c in codes if len(c) != 6 or c[2] not in "CZ")
    if unknown:
        raise SourceError(f"area codes of an unknown kind: {unknown}")
    return sorted(c for c in codes if c[2] == "C"), sorted(c for c in codes if c[2] == "Z")


def _rows(payload: dict, key: str) -> list[dict]:
    rows = payload.get(key)
    if not isinstance(rows, list):
        raise SourceError(f"warning archive response has no '{key}' list; keys were {sorted(payload)}")
    return rows


def _parse_rows(rows: list[dict], matched_by: str) -> ParsedEvents:
    events: list[WarningEvent] = []
    skipped: list[SkippedRecord] = []
    for row in rows:
        issue = _utc(row["issue"])
        expire = _utc(row["expire"])
        if expire <= issue:
            # Seen in real data: a watch withdrawn before it was due to start.
            # It was never in force, so it carries no time.
            skipped.append(SkippedRecord("expiry_not_after_issue", row))
            continue
        year = _VTEC_YEAR.search(row["url"])
        if year is None:
            raise SourceError(f"no event year in record url {row['url']!r}")
        events.append(
            WarningEvent(
                matched_by=matched_by,
                wfo=row["wfo"],
                vtec_year=int(year.group(1)),
                phenomena=row["phenomena"],
                significance=row["significance"],
                event_id=int(row["eventid"]),
                ugc=row["ugc"] if matched_by == "zone" else None,
                issue_utc=issue,
                expire_utc=expire,
                name=row["name"],
            )
        )
    return ParsedEvents(events, skipped)


def _utc(text: str) -> datetime:
    """Read a UTC time. The two services write it as ...T15:36:00Z and ...T14:36Z."""
    moment = datetime.fromisoformat(text)
    if moment.utcoffset() != timedelta(0):
        raise SourceError(f"expected a UTC time, got {text!r}")
    return moment
