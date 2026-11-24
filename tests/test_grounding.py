"""The grounding check (plan section 8.4, check 4), with planted wrong numbers."""

import pytest

from wra.agent.grounding import numbers_in_text, source_numbers, ungrounded

RESULT = {
    "data": {"rows": [{"hub_id": "MSP", "value": 2.71, "rank": 1}, {"hub_id": "MCI", "value": 1.44, "rank": 2}],
             "pct_of_observed": 7.1, "days_meeting": 26, "days_observed": 364},
    "display": {"title": "Denver (DEN): days with measurable snowfall, 2025", "notes": ["almost 8 mph below normal"],
                "rows": [["Days with 0.1 in or more", 26]]},
    "provenance": {"period": "2016-2025; hurricanes 1851-2024", "data_as_of": "2026-11-24"},
}  # fmt: skip


def test_numbers_are_read_with_their_decimals():
    assert numbers_in_text("Minneapolis 2.71, Kansas City 1.44 (7.1%); 1,258 warnings; 6th of 12.") == [
        ("2.71", 2.71, 2), ("1.44", 1.44, 2), ("7.1", 7.1, 1), ("1,258", 1258.0, 0), ("6", 6.0, 0), ("12", 12.0, 0),
    ]  # fmt: skip


def test_a_range_and_a_date_are_separate_numbers():
    assert [n for _, n, _ in numbers_in_text("2016-2025, as of 2026-11-24")] == [2016, 2025, 2026, 11, 24]


def test_source_numbers_come_from_values_and_from_text_inside_results_and_arguments():
    found = source_numbers([RESULT], [{"top_n": 3}])
    assert {2.71, 1.44, 7.1, 26, 364, 2016, 2025, 1851, 2024, 8, 0.1, 3} <= found


def test_figures_from_the_results_pass_including_rounded_ones():
    text = "Minneapolis leads at 2.71 days, about 2.7; Kansas City has 1.4. Denver: 7.1% (26 of 364), 2016 to 2025."
    assert ungrounded(text, [RESULT], []) == []


@pytest.mark.parametrize("planted", ["2.81", "2.6", "27", "7.2%", "365", "1.45"])
def test_a_planted_wrong_number_is_caught(planted):
    assert ungrounded(f"Minneapolis is at {planted} days.", [RESULT], []) == [planted.rstrip("%")]


def test_rounding_works_only_to_the_decimals_written():
    # 2.71 rounds to 3 at no decimals, so "3" is grounded; "2.8" is not, at one decimal.
    assert ungrounded("about 3 days", [RESULT], []) == []
    assert ungrounded("about 2.8 days", [RESULT], []) == ["2.8"]


def test_an_argument_counts_as_a_source():
    assert ungrounded("With hurricanes counted 2 times", [RESULT], [{"value": 2}]) == []


def test_text_without_digits_has_nothing_to_check():
    assert ungrounded("Roughly twice as exposed.", [RESULT], []) == []
