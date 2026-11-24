"""The network half of the ingest: ask the public services and keep each response as received.

Per hub, four requests in a fixed order. The first, to the station service,
tells us where the hub is; the other three are asked about that point.

Everything is written to a staging folder and swapped in only when every
request has succeeded and parsed. A failed refresh leaves the old files alone.
"""

import json
import shutil
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import httpx

from wra.hubs import Hub
from wra.ingest import PERIOD_END, PERIOD_START, WARNINGS_ISSUED_BEFORE, WARNINGS_ISSUED_FROM, acis, fema_nri, iem
from wra.ingest.raw import RawStore

USER_AGENT = "weather-risk-agent/0.1"
PAUSE_SECONDS = 1.0  # between requests, to be polite to free public services
ATTEMPTS = 3

Get = Callable[[str, dict[str, str]], tuple[str, bytes]]


def refresh(
    hubs: list[Hub],
    raw_dir: Path,
    get: Get | None = None,
    pause: Callable[[float], None] = time.sleep,
    now: Callable[[], str] | None = None,
) -> None:
    """Fetch every hub's data again and replace the raw cache with it."""
    fetched_at = (now or _utc_now)()
    staging = raw_dir.with_name(raw_dir.name + ".new")
    if staging.exists():
        shutil.rmtree(staging)
    try:
        store = RawStore(staging)
        if get is None:
            with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=120.0) as client:
                _fetch_all(hubs, store, _http_get(client, pause), pause, fetched_at)
        else:
            _fetch_all(hubs, store, get, pause, fetched_at)
        store.write_manifest()
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    staging.rename(raw_dir)


def _fetch_all(hubs: list[Hub], store: RawStore, get: Get, pause: Callable[[float], None], fetched_at: str) -> None:
    for hub in hubs:
        # Each response is parsed before it is kept, so a bad one stops the refresh here.
        url, body = get(acis.DATA_URL, acis.request_params(hub.station, PERIOD_START, PERIOD_END))
        station, _ = acis.parse_station(json.loads(body), hub.station)
        store.save("acis", hub.id, url, body, fetched_at)
        pause(PAUSE_SECONDS)

        url, body = get(fema_nri.QUERY_URL, fema_nri.request_params(station.lat, station.lon))
        fema_nri.parse_county(json.loads(body))
        store.save("fema_nri", hub.id, url, body, fetched_at)
        pause(PAUSE_SECONDS)

        point = iem.request_params(station.lat, station.lon, WARNINGS_ISSUED_FROM, WARNINGS_ISSUED_BEFORE)
        url, body = get(iem.ZONE_URL, point)
        iem.parse_zone_response(json.loads(body))
        store.save("iem_zone", hub.id, url, body, fetched_at)
        pause(PAUSE_SECONDS)

        url, body = get(iem.POLYGON_URL, point)
        iem.parse_polygon_response(json.loads(body), station.lat, station.lon)
        store.save("iem_polygon", hub.id, url, body, fetched_at)
        pause(PAUSE_SECONDS)


def _http_get(client: httpx.Client, pause: Callable[[float], None]) -> Get:
    def get(url: str, params: dict[str, str]) -> tuple[str, bytes]:
        for attempt in range(1, ATTEMPTS + 1):
            try:
                response = client.get(url, params=params)
                response.raise_for_status()
                return str(response.url), response.content
            except (httpx.TransportError, httpx.HTTPStatusError):
                if attempt == ATTEMPTS:
                    raise
                pause(5.0 * attempt)
        raise AssertionError("unreachable")

    return get


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
