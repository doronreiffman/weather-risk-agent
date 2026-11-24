"""Parsers for the three data sources, tested on recorded responses.

Every fixture row is a real row fetched on 2026-11-24 for Dallas Love Field,
unchanged. Only the number of rows was cut.
"""

import json
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from wra.ingest import acis, fema_nri, iem
from wra.ingest.errors import SourceError
from wra.ingest.points import checked_point

FIXTURES = Path(__file__).parent / "fixtures"

# Dallas Love Field, as the station service reports it.
DAL_LAT, DAL_LON = 32.83839, -96.83583


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def utc(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=timezone.utc)


# --- the coordinate guard -------------------------------------------------
# A request with empty coordinates returned 926 records and no error
# (docs/PLAN.md, section 12), so no request is built without a checked point.


@pytest.mark.parametrize(
    "lat, lon",
    [
        (None, DAL_LON),
        (DAL_LAT, None),
        ("", ""),
        (float("nan"), DAL_LON),
        (DAL_LON, DAL_LAT),  # swapped: the station service lists longitude first
        (0.0, 0.0),
        (True, DAL_LON),
    ],
)
def test_point_guard_refuses_missing_or_implausible_coordinates(lat, lon):
    with pytest.raises(ValueError):
        checked_point(lat, lon)


def test_point_guard_accepts_a_hub_location():
    assert checked_point(DAL_LAT, DAL_LON) == (DAL_LAT, DAL_LON)


@pytest.mark.parametrize(
    "build",
    [
        lambda: iem.request_params(None, None, date(2016, 1, 1), date(2025, 12, 31)),
        lambda: fema_nri.request_params("", ""),
    ],
)
def test_no_request_is_built_from_empty_coordinates(build):
    with pytest.raises(ValueError):
        build()


def test_iem_request_carries_the_point_and_the_period():
    params = iem.request_params(DAL_LAT, DAL_LON, date(2016, 1, 1), date(2025, 12, 31))

    assert params == {
        "lat": "32.83839",
        "lon": "-96.83583",
        "sdate": "2016-01-01",
        "edate": "2025-12-31",
    }


# --- warning archive: warnings by forecast zone or county ------------------


def test_zone_response_gives_one_event_per_row_with_utc_times():
    parsed = iem.parse_zone_response(load("iem_zone_DAL.json"))

    winter_storm = next(e for e in parsed.events if e.phenomena == "WS")
    assert winter_storm == iem.WarningEvent(
        matched_by="zone",
        wfo="FWD",
        vtec_year=2021,
        phenomena="WS",
        significance="W",
        event_id=3,
        ugc="TXZ119",
        issue_utc=utc(2021, 2, 13, 12, 0),
        expire_utc=utc(2021, 2, 15, 15, 0),
        name="Winter Storm Warning",
    )


def test_records_with_expiry_before_issue_are_skipped_and_reported():
    # Two real records: a Fire Weather Watch due to start at 15:00 and withdrawn
    # at 10:28, and a Flood Warning due at 18:00 and ended at 01:13 the same day.
    parsed = iem.parse_zone_response(load("iem_zone_DAL.json"))

    assert len(parsed.events) == 8
    assert [(s.reason, s.record["name"], s.record["issue"], s.record["expire"]) for s in parsed.skipped] == [
        ("expiry_not_after_issue", "Fire Weather Watch", "2016-02-08T15:00:00Z", "2016-02-08T10:28:00Z"),
        ("expiry_not_after_issue", "Flood Warning", "2016-03-16T18:00:00Z", "2016-03-16T01:13:00Z"),
    ]
    assert all(e.expire_utc > e.issue_utc for e in parsed.events)


def test_event_number_year_comes_from_the_record_not_the_issue_date():
    # A flood warning numbered in 2015 that reached this county on 2016-01-01.
    parsed = iem.parse_zone_response(load("iem_zone_DAL.json"))

    first = parsed.events[0]
    assert (first.vtec_year, first.event_id) == (2015, 320)
    assert first.issue_utc == utc(2016, 1, 1, 15, 36)


def test_a_warning_listed_twice_is_kept_as_two_intervals():
    # The same flood warning reached the county at two different times.
    # Merging overlaps is the scoring code's job, so both rows survive here.
    parsed = iem.parse_zone_response(load("iem_zone_DAL.json"))

    twice = [e for e in parsed.events if (e.vtec_year, e.phenomena, e.event_id) == (2017, "FL", 27)]
    assert [e.issue_utc for e in twice] == [utc(2017, 6, 24, 6, 51), utc(2017, 6, 24, 18, 12)]


def test_area_codes_are_split_into_county_and_zone():
    parsed = iem.parse_zone_response(load("iem_zone_DAL.json"))

    assert iem.area_codes(parsed.events) == (["TXC113"], ["TXZ119"])


def test_an_area_code_that_is_neither_county_nor_zone_is_an_error():
    parsed = iem.parse_zone_response(load("iem_zone_DAL.json"))
    odd = [replace(parsed.events[0], ugc="TXX113")]

    with pytest.raises(SourceError, match="TXX113"):
        iem.area_codes(odd)


def test_zone_response_without_its_events_list_is_an_error():
    with pytest.raises(SourceError):
        iem.parse_zone_response({"generated_at": "2026-11-24T10:03:00Z"})


# --- warning archive: warnings whose drawn area covered the point ----------


def test_polygon_response_reads_the_shorter_time_format_and_has_no_area_code():
    parsed = iem.parse_polygon_response(load("iem_polygon_DAL.json"), DAL_LAT, DAL_LON)

    tornado = next(e for e in parsed.events if e.phenomena == "TO")
    assert tornado.matched_by == "polygon"
    assert tornado.ugc is None
    assert tornado.issue_utc == utc(2019, 10, 21, 2, 0)
    assert tornado.expire_utc == utc(2019, 10, 21, 2, 30)
    assert [e.phenomena for e in parsed.events] == ["SV", "FA", "FF", "TO"]
    assert parsed.skipped == []


def test_polygon_response_for_a_different_point_is_refused():
    # The service echoes the point it answered for. If that is not the point
    # we asked about, the data belongs to somewhere else.
    with pytest.raises(SourceError, match="different point"):
        iem.parse_polygon_response(load("iem_polygon_DAL.json"), 25.78805, -80.31694)


# --- FEMA National Risk Index ---------------------------------------------


def test_fema_request_asks_for_the_county_containing_the_point():
    params = fema_nri.request_params(DAL_LAT, DAL_LON)

    assert params["geometry"] == "-96.83583,32.83839"  # longitude first
    assert params["geometryType"] == "esriGeometryPoint"
    assert params["inSR"] == "4326"
    assert "HRCN_AFREQ" in params["outFields"].split(",")


def test_fema_county_figures_are_read_with_the_release_name():
    county = fema_nri.parse_county(load("fema_point_DAL.json"))

    assert county.county_fips == "48113"
    assert county.county_name == "Dallas"
    assert county.state == "TX"
    assert county.release == "December 2025"
    assert county.frequencies["HRCN_AFREQ"] == pytest.approx(0.0115269, abs=1e-7)
    # FEMA gives no coastal flooding figure for an inland county.
    assert county.frequencies["CFLD_AFREQ"] is None
    assert county.county_ugc == "TXC113"


def test_fema_error_body_raises_even_though_the_status_was_200():
    with pytest.raises(SourceError, match="Invalid query parameters"):
        fema_nri.parse_county(load("fema_error.json"))


def test_fema_point_outside_every_county_raises():
    with pytest.raises(SourceError, match="expected exactly one county"):
        fema_nri.parse_county(load("fema_no_county.json"))


# --- NOAA station observations (ACIS) --------------------------------------


def test_station_metadata_gives_latitude_and_longitude_the_right_way_round():
    station, _ = acis.parse_station(load("acis_DAL.json"), "DAL")

    assert station.name == "DALLAS FAA AP"
    assert (station.lat, station.lon) == (DAL_LAT, DAL_LON)
    assert station.county_fips == "48113"
    assert station.state == "TX"
    assert station.utc_offset_hours == -6.0


def test_station_days_keep_trace_and_missing_apart_from_zero():
    _, days = acis.parse_station(load("acis_DAL.json"), "DAL")
    by_day = {d.day: d for d in days}

    plain = by_day[date(2016, 1, 1)]
    assert (plain.snow_in, plain.snow_flag, plain.precip_in, plain.precip_flag) == (0.0, "", 0.0, "")

    trace_snow = by_day[date(2016, 1, 21)]
    assert (trace_snow.snow_in, trace_snow.snow_flag) == (0.0, "T")
    assert (trace_snow.precip_in, trace_snow.precip_flag) == (0.29, "")

    missing_snow = by_day[date(2025, 2, 27)]
    assert (missing_snow.snow_in, missing_snow.snow_flag) == (None, "M")
    assert (missing_snow.precip_in, missing_snow.precip_flag) == (0.19, "")

    missing_rain = by_day[date(2025, 9, 7)]
    assert (missing_rain.precip_in, missing_rain.precip_flag) == (None, "M")

    measurable = by_day[date(2021, 2, 14)]
    assert (measurable.snow_in, measurable.snow_flag) == (2.5, "")
    assert len(days) == 11


def test_station_value_with_an_unknown_code_raises_instead_of_guessing():
    payload = load("acis_DAL.json")
    payload["data"][0][1] = "0.3X"

    with pytest.raises(SourceError, match="0.3X"):
        acis.parse_station(payload, "DAL")


def test_station_error_body_raises_even_though_the_status_was_200():
    with pytest.raises(SourceError, match="no data available"):
        acis.parse_station(load("acis_error.json"), "NOSUCHSTATION")


def test_station_response_for_a_different_station_is_refused():
    with pytest.raises(SourceError, match="different station"):
        acis.parse_station(load("acis_DAL.json"), "DFW")
