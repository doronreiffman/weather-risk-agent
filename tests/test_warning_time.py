"""Time under warning, on hand-built warning lists with answers worked out by hand."""

from datetime import UTC, datetime

import pytest

from wra.ingest.iem import WarningEvent
from wra.scoring.warning_time import counted_spells, days_by_year, hours_by_year, merge_spells

WINTER = (["WS", "BZ", "IS", "LE"], [])
SEVERE = ([], ["TO", "SV"])
FLOOD = (["CF"], ["FF"])


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def row(
    issue: str,
    expire: str,
    phenomena: str = "WS",
    matched_by: str = "zone",
    ugc: str | None = "TXZ119",
    significance: str = "W",
    event_id: int = 1,
    wfo: str = "FWD",
    vtec_year: int = 2021,
) -> WarningEvent:
    return WarningEvent(
        matched_by=matched_by,
        wfo=wfo,
        vtec_year=vtec_year,
        phenomena=phenomena,
        significance=significance,
        event_id=event_id,
        ugc=None if matched_by == "polygon" else ugc,
        issue_utc=utc(issue),
        expire_utc=utc(expire),
        name="test",
    )


# --- merging -------------------------------------------------------------------------------


def test_overlapping_spells_merge_into_one():
    spells = [(utc("2021-02-01T00:00"), utc("2021-02-01T10:00")), (utc("2021-02-01T06:00"), utc("2021-02-01T12:00"))]
    assert merge_spells(spells) == [(utc("2021-02-01T00:00"), utc("2021-02-01T12:00"))]


def test_duplicate_spells_count_once():
    spell = (utc("2021-02-01T00:00"), utc("2021-02-01T10:00"))
    assert merge_spells([spell, spell, spell]) == [spell]


def test_touching_spells_merge_and_separate_ones_stay_apart_whatever_the_input_order():
    later = (utc("2021-03-01T00:00"), utc("2021-03-01T02:00"))
    first = (utc("2021-02-01T00:00"), utc("2021-02-01T05:00"))
    touching = (utc("2021-02-01T05:00"), utc("2021-02-01T08:00"))
    assert merge_spells([later, touching, first]) == [(first[0], touching[1]), later]


def test_a_spell_inside_another_adds_nothing():
    outer = (utc("2021-02-01T00:00"), utc("2021-02-02T00:00"))
    inner = (utc("2021-02-01T03:00"), utc("2021-02-01T04:00"))
    assert merge_spells([outer, inner]) == [outer]


# --- hours per local year ------------------------------------------------------------------


def test_a_warning_crossing_new_year_is_split_at_local_midnight():
    # 22:00 on 31 Dec 2020 to 04:00 on 1 Jan 2021 in Dallas (UTC-6 in winter).
    # In UTC the whole spell falls in 2021; in the hub's time zone 2 hours belong to 2020.
    spells = [(utc("2021-01-01T04:00"), utc("2021-01-01T10:00"))]
    assert hours_by_year(spells, "America/Chicago", 2020, 2021) == {2020: 2.0, 2021: 4.0}


def test_hours_outside_the_period_are_dropped_in_the_hubs_time_zone():
    spells = [
        # 20:00 on 31 Dec 2015 to 02:00 on 1 Jan 2016, Chicago time: only the 2 hours in 2016 count.
        (utc("2016-01-01T02:00"), utc("2016-01-01T08:00")),
        # 20:00 to 23:00 on 31 Dec 2025, Chicago time, though 2026 in UTC: all 3 hours count, in 2025.
        (utc("2026-01-01T02:00"), utc("2026-01-01T05:00")),
        # 1 Jan 2026 local: outside the period.
        (utc("2026-01-01T07:00"), utc("2026-01-01T09:00")),
    ]
    assert hours_by_year(spells, "America/Chicago", 2016, 2025) == {
        2016: 2.0, 2017: 0.0, 2018: 0.0, 2019: 0.0, 2020: 0.0,
        2021: 0.0, 2022: 0.0, 2023: 0.0, 2024: 0.0, 2025: 3.0,
    }  # fmt: skip


def test_a_year_with_no_warnings_is_present_as_zero():
    assert hours_by_year([], "America/Denver", 2016, 2017) == {2016: 0.0, 2017: 0.0}


def test_hours_are_real_elapsed_hours_across_a_clock_change():
    # 00:00 to 06:00 local on 14 Mar 2021, when Chicago clocks jump from 02:00 to 03:00:
    # 5 real hours. The spell is stored in UTC, so the count is exact.
    spells = [(utc("2021-03-14T06:00"), utc("2021-03-14T11:00"))]
    assert hours_by_year(spells, "America/Chicago", 2021, 2021) == {2021: 5.0}


# --- which rows count ----------------------------------------------------------------------


def test_only_warnings_of_the_hazards_types_count():
    rows = [
        row("2021-02-01T00:00", "2021-02-01T10:00", phenomena="WS"),
        row("2021-02-01T00:00", "2021-02-01T10:00", phenomena="WS", significance="A", event_id=2),  # watch
        row("2021-02-01T00:00", "2021-02-01T10:00", phenomena="WW", significance="Y", event_id=3),  # advisory
        row("2021-02-02T00:00", "2021-02-02T10:00", phenomena="WC", event_id=4),  # wind chill: not scored
    ]
    assert counted_spells(rows, *WINTER) == [(utc("2021-02-01T00:00"), utc("2021-02-01T10:00"))]


def test_zone_codes_count_only_from_forecast_zone_rows():
    rows = [
        row("2021-02-01T00:00", "2021-02-01T10:00", ugc="TXZ119"),
        row("2021-02-05T00:00", "2021-02-05T10:00", ugc="TXC113", event_id=2),  # county row
    ]
    assert counted_spells(rows, *WINTER) == [(utc("2021-02-01T00:00"), utc("2021-02-01T10:00"))]


def test_storm_warnings_count_only_from_drawn_area_rows():
    # A severe thunderstorm warning elsewhere in the county shows only as a county row.
    rows = [
        row("2021-05-01T20:00", "2021-05-01T21:00", phenomena="SV", ugc="TXC113", event_id=7),
        row("2021-05-02T20:00", "2021-05-02T20:45", phenomena="SV", matched_by="polygon", event_id=8),
        row("2021-05-02T20:00", "2021-05-02T20:45", phenomena="SV", ugc="TXC113", event_id=8),
    ]
    assert counted_spells(rows, *SEVERE) == [(utc("2021-05-02T20:00"), utc("2021-05-02T20:45"))]


def test_a_cancelled_storm_warning_ends_when_its_county_row_ends():
    rows = [
        row("2021-05-02T20:00", "2021-05-02T21:00", phenomena="SV", matched_by="polygon", event_id=8),
        row("2021-05-02T20:00", "2021-05-02T20:20", phenomena="SV", ugc="TXC113", event_id=8),
    ]
    assert counted_spells(rows, *SEVERE) == [(utc("2021-05-02T20:00"), utc("2021-05-02T20:20"))]


def test_an_extension_in_the_county_row_is_not_added():
    rows = [
        row("2021-06-01T01:00", "2021-06-01T04:00", phenomena="FF", matched_by="polygon", event_id=3),
        row("2021-06-01T01:00", "2021-06-01T07:00", phenomena="FF", ugc="TXC113", event_id=3),
    ]
    assert counted_spells(rows, *FLOOD) == [(utc("2021-06-01T01:00"), utc("2021-06-01T04:00"))]


def test_the_county_row_must_be_the_same_warning():
    # Same event number, but another office, year or type: not the same warning.
    polygon = row("2021-05-02T20:00", "2021-05-02T21:00", phenomena="SV", matched_by="polygon", event_id=8)
    others = [
        row("2021-05-02T20:00", "2021-05-02T20:10", phenomena="SV", ugc="TXC113", event_id=8, wfo="SHV"),
        row("2021-05-02T20:00", "2021-05-02T20:10", phenomena="SV", ugc="TXC113", event_id=8, vtec_year=2020),
        row("2021-05-02T20:00", "2021-05-02T20:10", phenomena="TO", ugc="TXC113", event_id=8),
    ]
    assert counted_spells([polygon, *others], *SEVERE) == [(utc("2021-05-02T20:00"), utc("2021-05-02T21:00"))]


def test_the_last_of_several_county_ends_is_used():
    rows = [
        row("2021-05-02T20:00", "2021-05-02T21:00", phenomena="SV", matched_by="polygon", event_id=8),
        row("2021-05-02T20:00", "2021-05-02T20:20", phenomena="SV", ugc="TXC113", event_id=8),
        row("2021-05-02T20:00", "2021-05-02T20:40", phenomena="SV", ugc="TXC113", event_id=8),
    ]
    assert counted_spells(rows, *SEVERE) == [(utc("2021-05-02T20:00"), utc("2021-05-02T20:40"))]


def test_a_warning_cancelled_before_it_reached_the_hub_carries_no_time():
    rows = [
        row("2021-05-02T20:00", "2021-05-02T21:00", phenomena="SV", matched_by="polygon", event_id=8),
        row("2021-05-02T19:00", "2021-05-02T19:50", phenomena="SV", ugc="TXC113", event_id=8),
    ]
    assert counted_spells(rows, *SEVERE) == []


def test_an_expiry_before_the_issue_time_carries_no_time():
    # The ingest already sets these aside; the scoring code does not rely on it.
    rows = [
        row("2021-02-01T10:00", "2021-02-01T04:00"),
        row("2021-02-03T10:00", "2021-02-03T10:00", event_id=2),
    ]
    assert counted_spells(rows, *WINTER) == []


# --- all together --------------------------------------------------------------------------


def test_days_per_year_merges_one_warning_listed_for_two_zones():
    # Denver's point sits in two zone codes over the years; one warning listed for both counts once.
    rows = [
        row("2021-03-13T12:00", "2021-03-15T00:00", ugc="COZ040"),  # 36 hours
        row("2021-03-13T12:00", "2021-03-15T00:00", ugc="COZ240"),
        row("2021-03-14T18:00", "2021-03-15T06:00", phenomena="BZ", ugc="COZ240", event_id=2),  # 6 more hours
    ]
    assert days_by_year(rows, *WINTER, tz="America/Denver", first_year=2021, last_year=2021) == {
        2021: pytest.approx(42 / 24)
    }
