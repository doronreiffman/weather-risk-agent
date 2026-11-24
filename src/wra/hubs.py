"""The hub list as typed in config/hubs.toml: who the hubs are.

Where a hub sits (coordinates, county, warning zones) is not typed. The ingest
reads it from the data sources and stores it in the database.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REGIONS = ("midwest", "south", "west")


@dataclass(frozen=True)
class Hub:
    id: str
    city: str
    state: str  # two-letter code
    region: str
    station: str  # the airport's id at the NOAA station service
    tz: str  # IANA time zone name


def load_hubs(path: Path) -> list[Hub]:
    with path.open("rb") as handle:
        hubs = [Hub(**row) for row in tomllib.load(handle)["hub"]]
    seen: set[str] = set()
    for hub in hubs:
        if hub.id in seen:
            raise ValueError(f"hub id {hub.id} appears more than once in {path}")
        seen.add(hub.id)
        if hub.region not in REGIONS:
            raise ValueError(f"hub {hub.id}: region {hub.region!r} is not one of {REGIONS}")
        try:
            ZoneInfo(hub.tz)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"hub {hub.id}: unknown time zone {hub.tz!r}") from error
    return hubs
