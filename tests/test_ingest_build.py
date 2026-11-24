"""The two halves of the ingest: fetching into the raw cache, and building the database from it."""

import json
import socket
import sqlite3
from dataclasses import replace
from datetime import date
from pathlib import Path

import httpx
import pytest

from wra.hubs import Hub
from wra.ingest import (
    PERIOD_END,
    PERIOD_START,
    WARNINGS_ISSUED_BEFORE,
    WARNINGS_ISSUED_FROM,
    acis,
    fema_nri,
    iem,
    store,
)
from wra.ingest.build import build_database
from wra.ingest.errors import SourceError
from wra.ingest.fetch import _http_get, refresh
from wra.ingest.raw import RawStore

FIXTURES = Path(__file__).parent / "fixtures"
DAL = Hub(id="DAL", city="Dallas", state="TX", region="south", station="DAL", tz="America/Chicago")
DAL_LAT, DAL_LON = 32.83839, -96.83583
FETCHED_AT = "2026-11-24T10:00:00Z"
WARNING_WINDOW = (WARNINGS_ISSUED_FROM, WARNINGS_ISSUED_BEFORE)

# What each service would be asked for Dallas, and the recorded answer.
REQUESTS = {
    "acis": (acis.DATA_URL, acis.request_params("DAL", PERIOD_START, PERIOD_END), "acis_DAL.json"),
    "fema_nri": (fema_nri.QUERY_URL, fema_nri.request_params(DAL_LAT, DAL_LON), "fema_point_DAL.json"),
    "iem_zone": (iem.ZONE_URL, iem.request_params(DAL_LAT, DAL_LON, *WARNING_WINDOW), "iem_zone_DAL.json"),
    "iem_polygon": (iem.POLYGON_URL, iem.request_params(DAL_LAT, DAL_LON, *WARNING_WINDOW), "iem_polygon_DAL.json"),
}


def full_url(url: str, params: dict[str, str]) -> str:
    from urllib.parse import urlencode

    return f"{url}?{urlencode(params)}"


def fixture_bytes(name: str, change=None) -> bytes:
    payload = json.loads((FIXTURES / name).read_text())
    if change:
        change(payload)
    return json.dumps(payload).encode()


def make_raw(directory: Path, changes: dict | None = None, urls: dict | None = None) -> Path:
    """A raw cache holding the recorded Dallas responses, optionally altered."""
    store = RawStore(directory)
    for source, (url, params, fixture) in REQUESTS.items():
        body = fixture_bytes(fixture, (changes or {}).get(source))
        store.save(source, "DAL", (urls or {}).get(source, full_url(url, params)), body, FETCHED_AT)
    store.write_manifest()
    return directory


def rows(db: Path, sql: str) -> list[tuple]:
    with sqlite3.connect(db) as connection:
        return connection.execute(sql).fetchall()


# --- building ----------------------------------------------------------------


def test_database_is_built_from_the_raw_files_with_the_network_cut(tmp_path, monkeypatch):
    raw = make_raw(tmp_path / "raw")
    db = tmp_path / "wra.sqlite"

    def no_network(*args, **kwargs):
        raise AssertionError("the build must not open a network connection")

    monkeypatch.setattr(socket, "socket", no_network)
    build_database([DAL], raw, db)

    assert rows(db, "SELECT hub_id, station_name, lat, lon, county_fips, county_name FROM hubs") == [
        ("DAL", "DALLAS FAA AP", DAL_LAT, DAL_LON, "48113", "Dallas")
    ]
    assert rows(db, "SELECT matched_by, count(*) FROM warning_events GROUP BY 1 ORDER BY 1") == [
        ("polygon", 4),
        ("zone", 8),
    ]
    assert rows(db, "SELECT issue_utc, expire_utc FROM warning_events WHERE phenomena = 'IS'") == [
        ("2023-02-01T12:00:00Z", "2023-02-02T15:00:00Z")
    ]
    assert rows(db, "SELECT source, reason, count(*) FROM skipped_records GROUP BY 1, 2") == [
        ("iem_zone", "expiry_not_after_issue", 2)
    ]
    assert rows(db, "SELECT count(*) FROM station_daily") == [(11,)]
    assert rows(db, "SELECT snow_in, snow_flag FROM station_daily WHERE day = '2025-02-27'") == [(None, "M")]
    assert rows(db, "SELECT round(value, 6) FROM fema_nri WHERE field = 'HRCN_AFREQ'") == [(0.011527,)]
    assert rows(db, "SELECT count(*), min(fetched_at) FROM fetch_log") == [(4, FETCHED_AT)]
    assert rows(db, "SELECT key, value FROM meta ORDER BY key") == [
        ("period_end", "2025-12-31"),
        ("period_start", "2016-01-01"),
        ("warnings_issued_before", "2026-01-02"),
        ("warnings_issued_from", "2015-12-25"),
    ]


def test_warnings_are_requested_beyond_the_period_on_both_sides():
    # The archive selects by issue date, end date excluded (measured 2026-11-24),
    # so a warning running into 1 January 2016, or issued on 31 December 2025,
    # needs a wider request than the period itself.
    params = REQUESTS["iem_zone"][1]

    assert date.fromisoformat(params["sdate"]) < PERIOD_START
    assert date.fromisoformat(params["edate"]) > date(2026, 1, 1)


def test_hub_row_records_where_each_source_puts_the_hub(tmp_path):
    db = tmp_path / "wra.sqlite"
    build_database([DAL], make_raw(tmp_path / "raw"), db)

    assert rows(
        db, "SELECT station_county_fips, county_fips, warning_county_codes, warning_zone_codes, county_check FROM hubs"
    ) == [("48113", "48113", "TXC113", "TXZ119", "agree")]


def test_a_county_disagreement_between_the_map_based_sources_is_recorded_not_hidden(tmp_path):
    def move_to_denton(payload):
        payload["features"][0]["attributes"]["STCOFIPS"] = "48121"

    db = tmp_path / "wra.sqlite"
    build_database([DAL], make_raw(tmp_path / "raw", changes={"fema_nri": move_to_denton}), db)

    assert rows(db, "SELECT county_check FROM hubs") == [("differ",)]


def test_the_station_service_s_typed_county_label_does_not_decide_the_check(tmp_path):
    # Real case: the station service labels O'Hare as Cook County, while its
    # coordinates sit in DuPage on both FEMA's map and the Weather Service's.
    def relabel(payload):
        payload["meta"]["county"] = "48121"

    db = tmp_path / "wra.sqlite"
    build_database([DAL], make_raw(tmp_path / "raw", changes={"acis": relabel}), db)

    assert rows(db, "SELECT county_fips, station_county_fips, county_check FROM hubs") == [
        ("48113", "48121", "agree")
    ]


def test_a_raw_file_changed_since_it_was_fetched_is_refused(tmp_path):
    raw = make_raw(tmp_path / "raw")
    (raw / "iem_zone" / "DAL.json").write_text('{"events": []}')

    with pytest.raises(SourceError, match="changed since it was fetched"):
        build_database([DAL], raw, tmp_path / "wra.sqlite")


def test_a_raw_file_fetched_for_another_point_is_refused(tmp_path):
    miami = full_url(iem.ZONE_URL, iem.request_params(25.78805, -80.31694, *WARNING_WINDOW))
    raw = make_raw(tmp_path / "raw", urls={"iem_zone": miami})

    with pytest.raises(SourceError, match="different request"):
        build_database([DAL], raw, tmp_path / "wra.sqlite")


def test_a_raw_file_fetched_for_another_period_is_refused(tmp_path):
    # The shape of the request made before 2026-11-24, which missed 31 December 2025.
    old = full_url(iem.POLYGON_URL, iem.request_params(DAL_LAT, DAL_LON, PERIOD_START, PERIOD_END))
    raw = make_raw(tmp_path / "raw", urls={"iem_polygon": old})

    with pytest.raises(SourceError, match="different request"):
        build_database([DAL], raw, tmp_path / "wra.sqlite")


def test_a_fema_county_in_another_state_is_refused(tmp_path):
    def move_to_oklahoma(payload):
        payload["features"][0]["attributes"]["STATEABBRV"] = "OK"

    raw = make_raw(tmp_path / "raw", changes={"fema_nri": move_to_oklahoma})

    with pytest.raises(SourceError, match="FEMA county is in OK"):
        build_database([DAL], raw, tmp_path / "wra.sqlite")


def test_a_mistyped_time_zone_is_refused(tmp_path):
    # Dallas typed as Mountain time: every warning hour near midnight would land in the wrong day.
    raw = make_raw(tmp_path / "raw")

    with pytest.raises(SourceError, match="time zone America/Denver"):
        build_database([replace(DAL, tz="America/Denver")], raw, tmp_path / "wra.sqlite")


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda p: p["data"].append(["2026-01-01", "0.0", "0.00"]), "outside"),
        (lambda p: p["data"].append(list(p["data"][0])), "more than once"),
    ],
)
def test_station_days_outside_the_period_or_repeated_are_refused(tmp_path, change, message):
    raw = make_raw(tmp_path / "raw", changes={"acis": change})

    with pytest.raises(SourceError, match=message):
        build_database([DAL], raw, tmp_path / "wra.sqlite")


def test_warnings_for_an_area_in_another_state_are_refused(tmp_path):
    def move_to_oklahoma(payload):
        payload["events"][0]["ugc"] = "OKC109"

    raw = make_raw(tmp_path / "raw", changes={"iem_zone": move_to_oklahoma})

    with pytest.raises(SourceError, match="OKC109"):
        build_database([DAL], raw, tmp_path / "wra.sqlite")


def test_a_missing_raw_file_says_how_to_get_it(tmp_path):
    with pytest.raises(SourceError, match="--refresh"):
        build_database([DAL], tmp_path / "empty", tmp_path / "wra.sqlite")


def test_a_build_that_fails_while_reading_leaves_the_previous_database_in_place(tmp_path):
    db = tmp_path / "wra.sqlite"
    build_database([DAL], make_raw(tmp_path / "raw"), db)
    before = db.read_bytes()

    with pytest.raises(SourceError):
        build_database([DAL], tmp_path / "empty", db)

    assert db.read_bytes() == before


def test_a_build_that_fails_while_writing_leaves_the_previous_database_and_no_staging_file(tmp_path, monkeypatch):
    db = tmp_path / "wra.sqlite"
    raw = make_raw(tmp_path / "raw")
    build_database([DAL], raw, db)
    before = db.read_bytes()

    def disk_full(connection, data):
        connection.execute("INSERT INTO meta VALUES ('half', 'written')")
        raise sqlite3.OperationalError("database or disk is full")

    monkeypatch.setattr(store, "_write_hub", disk_full)
    with pytest.raises(sqlite3.OperationalError):
        build_database([DAL], raw, db)

    assert db.read_bytes() == before
    assert not (tmp_path / "wra.sqlite.new").exists()


# --- fetching ----------------------------------------------------------------


class FakeService:
    """Stands in for the network: answers each request with the recorded response.

    `station_at` moves the station: its metadata reports that point, and the
    polygon service echoes it back, as the real services would.
    """

    def __init__(self, fail_on: str | None = None, station_at: tuple[float, float] | None = None):
        self.asked: list[tuple[str, dict]] = []
        self.fail_on = fail_on
        self.station_at = station_at

    def __call__(self, url: str, params: dict[str, str]) -> tuple[str, bytes]:
        self.asked.append((url, params))
        if url == self.fail_on:
            raise ConnectionError("service is down")
        fixture = next(name for base, _, name in REQUESTS.values() if base == url)
        return full_url(url, params), fixture_bytes(fixture, self._move if self.station_at else None)

    def _move(self, payload: dict) -> None:
        lat, lon = self.station_at
        if "meta" in payload:
            payload["meta"]["ll"] = [lon, lat]
        if "sbws" in payload:
            payload["lat"], payload["lon"] = lat, lon


def test_refresh_asks_every_source_about_the_point_the_station_reports(tmp_path):
    # Move the station: if any request still used the typed Dallas point, this would fail.
    moved = (32.9, -96.9)
    service = FakeService(station_at=moved)

    refresh([DAL], tmp_path / "raw", get=service, pause=lambda seconds: None, now=lambda: FETCHED_AT)

    assert service.asked == [
        (acis.DATA_URL, acis.request_params("DAL", PERIOD_START, PERIOD_END)),
        (fema_nri.QUERY_URL, fema_nri.request_params(*moved)),
        (iem.ZONE_URL, iem.request_params(*moved, *WARNING_WINDOW)),
        (iem.POLYGON_URL, iem.request_params(*moved, *WARNING_WINDOW)),
    ]


def test_refreshed_files_build_a_database(tmp_path):
    refresh([DAL], tmp_path / "raw", get=FakeService(), pause=lambda seconds: None, now=lambda: FETCHED_AT)

    db = tmp_path / "wra.sqlite"
    build_database([DAL], tmp_path / "raw", db)
    assert rows(db, "SELECT count(*) FROM warning_events") == [(12,)]


def test_refresh_pauses_between_requests(tmp_path):
    pauses: list[float] = []

    refresh([DAL], tmp_path / "raw", get=FakeService(), pause=pauses.append, now=lambda: FETCHED_AT)

    assert pauses == [1.0, 1.0, 1.0, 1.0]


def test_a_failed_refresh_keeps_the_previous_raw_files(tmp_path):
    raw = make_raw(tmp_path / "raw")
    before = {p.relative_to(raw): p.read_bytes() for p in sorted(raw.rglob("*")) if p.is_file()}

    with pytest.raises(ConnectionError):
        refresh(
            [DAL], raw, get=FakeService(fail_on=iem.POLYGON_URL), pause=lambda s: None, now=lambda: "2027-01-01T00:00:00Z"
        )

    after = {p.relative_to(raw): p.read_bytes() for p in sorted(raw.rglob("*")) if p.is_file()}
    assert after == before
    assert not (tmp_path / "raw.new").exists()


# --- the HTTP layer ----------------------------------------------------------


def answering(*statuses: int):
    """A fake server that answers with these statuses in turn; 200 carries a small body."""
    replies = iter(statuses)

    def handle(request: httpx.Request) -> httpx.Response:
        status = next(replies)
        return httpx.Response(status, content=b'{"ok": 1}' if status == 200 else b"busy")

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_a_busy_server_is_retried_after_a_pause():
    pauses: list[float] = []
    get = _http_get(answering(503, 200), pauses.append)

    url, body = get("https://example.test/data", {"a": "1"})

    assert body == b'{"ok": 1}'
    assert url == "https://example.test/data?a=1"
    assert pauses == [5.0]


def test_a_server_that_stays_busy_raises_after_three_attempts():
    pauses: list[float] = []
    get = _http_get(answering(503, 503, 503), pauses.append)

    with pytest.raises(httpx.HTTPStatusError):
        get("https://example.test/data", {})
    assert pauses == [5.0, 10.0]
