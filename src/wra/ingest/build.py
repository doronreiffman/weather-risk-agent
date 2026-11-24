"""The offline half of the ingest: read the raw cache, check it, write the database.

Nothing here touches the network. The checks answer one question for every
stored response: is this really the data for this hub?

- Hard stops (SourceError): the file changed after it was fetched; it answers
  a different request than the one we would send today (another point, another
  period); a station, county or warning area lies in another state.
- Recorded, not stopped: FEMA and the warning archive naming different counties
  for the hub. Both answer from the map, so they should agree; if they do not, a
  person needs to look, and the data report says so. The station service's own
  county label is stored too, but it is a typed label and not a map lookup: for
  O'Hare and Atlanta it names the neighbouring county.
"""

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from wra.hubs import Hub
from wra.ingest import PERIOD_END, PERIOD_START, acis, fema_nri, iem
from wra.ingest.errors import SourceError
from wra.ingest.raw import SOURCES, FetchRecord, RawStore
from wra.ingest.store import write_database


@dataclass(frozen=True)
class HubData:
    """Everything the sources say about one hub, parsed and checked."""

    hub: Hub
    station: acis.Station
    days: list[acis.DailyObs]
    county: fema_nri.NriCounty
    zone: iem.ParsedEvents
    polygon: iem.ParsedEvents
    county_codes: list[str]  # as the warning archive names the hub's county
    zone_codes: list[str]
    fetches: list[FetchRecord]

    @property
    def county_check(self) -> str:
        """Do FEMA and the warning archive, the two map-based sources, name the same county?"""
        return "agree" if self.county_codes == [self.county.county_ugc] else "differ"


def build_database(hubs: list[Hub], raw_dir: Path, db_path: Path) -> list[HubData]:
    """Rebuild the database from the raw cache. Returns what was loaded, for reporting."""
    store = RawStore(raw_dir)
    loaded = [load_hub(hub, store) for hub in hubs]
    write_database(db_path, loaded, PERIOD_START, PERIOD_END)
    return loaded


def load_hub(hub: Hub, store: RawStore) -> HubData:
    payloads = {source: store.load(source, hub.id) for source in SOURCES}

    payload, record = payloads["acis"]
    _same_request(record, acis.request_params(hub.station, PERIOD_START, PERIOD_END))
    station, days = acis.parse_station(payload, hub.station)
    _same_state(hub, "station", station.state)

    payload, record = payloads["fema_nri"]
    _same_request(record, fema_nri.request_params(station.lat, station.lon))
    county = fema_nri.parse_county(payload)
    _same_state(hub, "FEMA county", county.state)

    point = iem.request_params(station.lat, station.lon, PERIOD_START, PERIOD_END)
    payload, record = payloads["iem_zone"]
    _same_request(record, point)
    zone = iem.parse_zone_response(payload)
    county_codes, zone_codes = iem.area_codes(zone.events)
    elsewhere = [code for code in county_codes + zone_codes if not code.startswith(hub.state)]
    if elsewhere:
        raise SourceError(f"{hub.id}: warnings for areas outside {hub.state}: {elsewhere}")

    payload, record = payloads["iem_polygon"]
    _same_request(record, point)
    polygon = iem.parse_polygon_response(payload, station.lat, station.lon)

    return HubData(
        hub=hub,
        station=station,
        days=days,
        county=county,
        zone=zone,
        polygon=polygon,
        county_codes=county_codes,
        zone_codes=zone_codes,
        fetches=[payloads[source][1] for source in SOURCES],
    )


def _same_request(record: FetchRecord, expected: dict[str, str]) -> None:
    """The stored response must answer exactly the request we would send today."""
    asked = dict(parse_qsl(urlsplit(record.url).query, keep_blank_values=True))
    if asked != expected:
        raise SourceError(
            f"stored {record.source} response for {record.hub_id} answers a different request: "
            f"stored {asked}, expected {expected}; run `wra ingest --refresh`"
        )


def _same_state(hub: Hub, what: str, state: str) -> None:
    if state != hub.state:
        raise SourceError(f"{hub.id}: {what} is in {state}, but the hub is configured in {hub.state}")
