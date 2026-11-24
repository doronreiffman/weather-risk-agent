"""The tools, on the database built from the committed raw responses, with "today" pinned to 2026-11-24."""

import json
from datetime import date

import pytest

from conftest import REPO
from wra.scoring.config import load_scoring_config
from wra.stored import load_stored
from wra.tools.context import ToolContext
from wra.tools.envelope import SOURCE_NAMES, ToolResult
from wra.tools.registry import TOOLS, run_tool

OVERALL_ORDER = ["MSP", "MEM", "DEN", "MCI", "ORD", "DAL", "IAH", "MIA", "IND", "ATL", "CMH", "PHX"]


@pytest.fixture(scope="module")
def ctx(real_db):
    return ToolContext(load_stored(real_db), load_scoring_config(REPO / "config" / "scoring.toml"), date(2026, 11, 24))


def rank_args(hazard="overall", region="all", top_n=None, weight_changes=()):
    return {"hazard": hazard, "region": region, "top_n": top_n, "weight_changes": list(weight_changes)}


def stats_args(hub_id="DEN", metric="snowfall", start_year=None, end_year=None, threshold="measurable"):
    return {"hub_id": hub_id, "metric": metric, "start_year": start_year, "end_year": end_year, "threshold": threshold}


def column(result: ToolResult, name: str) -> list:
    i = result.display.columns.index(name)
    return [row[i] for row in result.display.rows]


# --- every tool -----------------------------------------------------------------------------


def test_six_tools_are_registered():
    assert sorted(TOOLS) == sorted(
        ["list_hubs", "rank_hubs", "compare_hubs", "explain_hub", "daily_weather_stats", "get_methodology"]
    )


@pytest.mark.parametrize(
    "name, args",
    [
        ("list_hubs", {"region": "all"}),
        ("rank_hubs", rank_args()),
        ("compare_hubs", {"hub_ids": ["MIA", "IAH"], "hazards": ["hurricane", "flood"]}),
        ("explain_hub", {"hub_id": "DAL"}),
        ("daily_weather_stats", stats_args()),
        ("get_methodology", {}),
    ],
)
def test_every_tool_returns_the_envelope_as_json(ctx, name, args):
    result = run_tool(ctx, name, args)
    assert result.ok, result.error
    again = ToolResult.model_validate(json.loads(result.model_dump_json()))
    assert again == result
    assert result.provenance.confidence in ("high", "medium", "low") and result.provenance.confidence_reason
    assert result.provenance.data_as_of == "2026-11-24"


def test_bad_arguments_come_back_as_an_error_result_not_an_exception(ctx):
    result = run_tool(ctx, "rank_hubs", {"hazard": "earthquake", "region": "all", "top_n": None, "weight_changes": []})
    assert not result.ok and result.error.code == "invalid_arguments"
    assert run_tool(ctx, "no_such_tool", {}).error.code == "unknown_tool"


# --- daily_weather_stats ------------------------------------------------------------------


def test_denver_last_year_matches_the_hand_check(ctx):
    # Pinned in plan section 10.2: Denver International, 2025, 26 days of 0.1 inch or more of 364 observed.
    result = run_tool(ctx, "daily_weather_stats", stats_args())
    d = result.data
    assert (d["period"], d["days_meeting"], d["days_observed"], d["days_missing"], d["days_trace"]) == (
        "2025", 26, 364, 1, 19,
    )  # fmt: skip
    assert d["pct_of_observed"] == 7.1
    assert result.provenance.confidence == "high"
    assert "0.1 inch" in result.display.what_counts


def test_trace_or_more_adds_the_trace_days(ctx):
    assert run_tool(ctx, "daily_weather_stats", stats_args(threshold="trace_or_more")).data["days_meeting"] == 45


def test_a_null_end_year_means_the_last_full_year(ctx):
    result = run_tool(ctx, "daily_weather_stats", stats_args(start_year=2020))
    assert result.data["period"] == "2020-2025"


def test_a_year_outside_the_data_is_refused_with_the_covered_range(ctx):
    result = run_tool(ctx, "daily_weather_stats", stats_args(start_year=2010, end_year=2010))
    assert not result.ok and result.error.code == "no_data_for_period"
    assert "2016 to 2025" in result.error.message


def test_an_unknown_hub_is_refused(ctx):
    result = run_tool(ctx, "daily_weather_stats", stats_args(hub_id="SEA"))
    assert result.error.code == "unknown_hub"
    assert "MSP" in result.error.message


def test_start_after_end_is_refused(ctx):
    assert run_tool(ctx, "daily_weather_stats", stats_args(start_year=2024, end_year=2020)).error.code == (
        "invalid_arguments"
    )


def test_rain_counts_any_recorded_amount_and_says_it_is_weather_not_disruption(ctx):
    result = run_tool(ctx, "daily_weather_stats", stats_args(hub_id="IAH", metric="precipitation"))
    assert "0.01 inch" in result.display.what_counts and "not disruption" in result.display.what_counts


# --- rank_hubs -----------------------------------------------------------------------------


def test_the_overall_ranking(ctx):
    result = run_tool(ctx, "rank_hubs", rank_args())
    assert [r["hub_id"] for r in result.data["rows"]] == OVERALL_ORDER
    assert result.data["rows"][0]["value"] == 2.90 and result.data["rows"][0]["band"] == "High"
    assert result.data["rows"][-2]["band"] == "Low"  # Columbus, 0.99
    assert result.provenance.confidence == "low"  # 10 of 11 gaps within year-to-year swings
    assert any("FHWA-HOP-16-044" in note for note in result.display.notes)
    assert any(note.startswith("With winter counted double, the top three are") for note in result.display.notes)


def test_the_midwest_winter_ranking_has_no_band(ctx):
    result = run_tool(ctx, "rank_hubs", rank_args(hazard="winter", region="midwest"))
    assert [r["hub_id"] for r in result.data["rows"]] == ["MSP", "MCI", "ORD", "IND", "CMH"]
    assert "Band" not in result.display.columns and "band" not in result.data["rows"][0]
    assert column(result, "Clear of next")[0] == "yes"  # Minneapolis stands clear of Kansas City
    assert result.provenance.confidence == "low"
    assert any("FHWA-HOP-16-044" in note for note in result.display.notes)


def test_a_top_three_tests_only_the_gaps_it_shows(ctx):
    result = run_tool(ctx, "rank_hubs", rank_args(top_n=3))
    assert [r["hub_id"] for r in result.data["rows"]] == OVERALL_ORDER[:3]
    assert result.data["gaps_tested"] == 2
    # Denver (2.21) against Kansas City (2.20), reported but not counted in the label.
    assert result.data["rows"][-1]["clear_of_next"] is False


def test_a_top_one_tests_the_first_against_the_second(ctx):
    result = run_tool(ctx, "rank_hubs", rank_args(hazard="winter", region="south", top_n=1))
    assert result.data["gaps_tested"] == 1
    assert result.data["rows"][0]["clear_of_next"] is False  # Memphis is within year-to-year swings of Dallas
    assert result.provenance.confidence != "high"


def test_a_what_if_carries_no_winter_doubled_note(ctx):
    change = [{"hazard": "winter", "mode": "multiply", "value": 2}]
    result = run_tool(ctx, "rank_hubs", rank_args(weight_changes=change))
    assert not any("counted double" in note for note in result.display.notes)
    assert any("FHWA-HOP-16-044" in note for note in result.display.notes)


def test_a_flood_ranking_carries_no_winter_note(ctx):
    result = run_tool(ctx, "rank_hubs", rank_args(hazard="flood"))
    assert not any("FHWA" in note for note in result.display.notes)


def test_a_hurricane_ranking_is_at_most_medium(ctx):
    result = run_tool(ctx, "rank_hubs", rank_args(hazard="hurricane"))
    assert [r["hub_id"] for r in result.data["rows"]][:2] == ["MIA", "IAH"]
    assert result.provenance.confidence == "medium"
    assert result.provenance.period == "1851-2024"


def test_a_what_if_is_labelled_and_leaves_the_official_weights_alone(ctx):
    official = dict(ctx.config.weights)
    result = run_tool(ctx, "rank_hubs", rank_args(weight_changes=[{"hazard": "hurricane", "mode": "multiply", "value": 2}]))
    assert result.provenance.is_what_if and result.data["is_what_if"]
    assert result.display.title.startswith("WHAT-IF (hurricanes weight x 2)")
    assert "Official rank" in result.display.columns
    assert result.data["weights"]["hurricane"] == 10.0
    assert ctx.config.weights == official
    again = run_tool(ctx, "rank_hubs", rank_args())
    assert not again.provenance.is_what_if and [r["hub_id"] for r in again.data["rows"]] == OVERALL_ORDER


def test_a_negative_weight_is_refused(ctx):
    change = [{"hazard": "flood", "mode": "set", "value": -1}]
    assert run_tool(ctx, "rank_hubs", rank_args(weight_changes=change)).error.code == "invalid_arguments"


# --- list_hubs and get_methodology ---------------------------------------------------------


def test_list_hubs_by_region(ctx):
    result = run_tool(ctx, "list_hubs", {"region": "midwest"})
    assert [h["hub_id"] for h in result.data["hubs"]] == ["ORD", "MSP", "MCI", "IND", "CMH"]
    assert result.provenance.confidence == "high"


def test_the_methodology_comes_from_the_config(ctx):
    result = run_tool(ctx, "get_methodology", {})
    assert result.data["weights"] == ctx.config.weights
    assert result.data["bands"]["cutoffs"] == [1.0, 2.0, 3.0]
    assert ctx.config.winter_note in result.display.notes
    assert all(limit in result.display.notes for limit in ctx.config.known_limits)


# --- compare_hubs --------------------------------------------------------------------------


def test_miami_and_houston_on_hurricanes_and_floods(ctx):
    result = run_tool(ctx, "compare_hubs", {"hub_ids": ["MIA", "IAH"], "hazards": ["hurricane", "flood"]})
    hurricane, flood = result.data["results"]["hurricane"], result.data["results"]["flood"]
    assert [(r["hub_id"], r["value"]) for r in hurricane] == [("MIA", 1.52), ("IAH", 0.92)]
    assert hurricane[1]["below_highest_by"] == 0.6 and hurricane[1]["ratio_to_highest"] == 0.61
    assert hurricane[1]["clear_of_highest"] is None  # cannot be tested
    assert [(r["hub_id"], r["value"]) for r in flood] == [("IAH", 0.47), ("MIA", 0.21)]
    assert flood[1]["clear_of_highest"] is True
    assert result.provenance.confidence == "medium"  # a hurricane gap caps it
    assert result.data["supporting"]["IAH"]["coastal_flood_warning_days_a_year"] > 0
    assert "Band" not in result.display.columns  # no overall figure asked for


@pytest.mark.parametrize(
    "hub_ids, code",
    [(["MIA"], "invalid_arguments"), (["MIA", "MIA"], "invalid_arguments"), (["MIA", "SEA"], "unknown_hub")],
)
def test_comparisons_need_two_to_four_different_known_hubs(ctx, hub_ids, code):
    assert run_tool(ctx, "compare_hubs", {"hub_ids": hub_ids, "hazards": ["flood"]}).error.code == code


# --- explain_hub ---------------------------------------------------------------------------


def test_dallas_is_explained_with_its_real_band_and_place(ctx):
    result = run_tool(ctx, "explain_hub", {"hub_id": "DAL"})
    d = result.data
    assert (d["total"], d["band"], d["rank"], d["of"]) == (2.02, "High", 6, 12)
    assert (d["above"]["hub_id"], d["below"]["hub_id"]) == ("ORD", "IAH")
    assert sum(h["share_pct"] for h in d["hazards"]) == pytest.approx(100, abs=1)
    assert result.provenance.confidence == "low"  # Dallas is within year-to-year swings of both neighbours
    assert any("FHWA-HOP-16-044" in note for note in result.display.notes)


def test_a_hub_without_a_fema_hurricane_figure_says_why(ctx):
    result = run_tool(ctx, "explain_hub", {"hub_id": "DEN"})
    hurricane = next(h for h in result.data["hazards"] if h["hazard"] == "hurricane")
    assert hurricane["edd"] == 0.0 and "Not Applicable" in hurricane["note"]
    assert any("Not Applicable" in note for note in result.display.notes)


# --- plain words: every term an analyst may not know is explained where it appears (O15) ----


MIA_IAH = {"hub_ids": ["MIA", "IAH"], "hazards": ["hurricane", "flood"]}


def test_the_snowfall_table_says_what_a_trace_is(ctx):
    what = run_tool(ctx, "daily_weather_stats", stats_args()).display.what_counts
    assert "A trace means snow fell, but too little to measure; trace days are counted apart." in what


def test_the_rain_table_says_what_a_trace_is(ctx):
    what = run_tool(ctx, "daily_weather_stats", stats_args(hub_id="IAH", metric="precipitation")).display.what_counts
    assert "A trace means some rain or snow fell, but too little to measure; trace days are counted apart." in what


def test_a_ranking_says_what_clear_of_next_means(ctx):
    what = run_tool(ctx, "rank_hubs", rank_args(hazard="winter", region="midwest")).display.what_counts
    assert "Clear of next: yes when the gap to the next hub is bigger than the uncertainty in the two hubs' " in what
    assert "Not testable" not in what  # no hurricane figure in this table


def test_a_hurricane_ranking_says_why_its_gaps_are_not_testable(ctx):
    result = run_tool(ctx, "rank_hubs", rank_args(hazard="hurricane"))
    assert set(column(result, "Clear of next")) == {"not testable"}
    assert "Not testable: FEMA gives one long-run hurricane figure with no yearly values." in result.display.what_counts


def test_a_comparison_says_what_clear_of_the_highest_means(ctx):
    what = run_tool(ctx, "compare_hubs", MIA_IAH).display.what_counts
    assert "Clear of the highest: yes when the gap below the most exposed hub is bigger than the uncertainty" in what
    assert "Not testable: FEMA gives one long-run hurricane figure" in what


def test_the_zone_notes_say_what_a_forecast_zone_is(ctx):
    notes = run_tool(ctx, "compare_hubs", MIA_IAH).display.notes
    zone_notes = [n for n in notes if "zone" in n]
    assert len(zone_notes) == 2  # tropical warnings, and Houston's coastal flood warnings
    assert all("forecast zone (a Weather Service warning area, usually a county or part of one)" in n for n in zone_notes)


def test_the_methodology_says_what_watches_advisories_and_the_left_out_flood_warnings_are(ctx):
    not_scored = run_tool(ctx, "get_methodology", {}).data["not_scored"]
    for words in [
        "Watches (the hazard is possible, not certain)",
        "advisories (less serious than a warning)",
        "river flood warnings (a river forecast to rise above its flood level at a set point)",
        "area flood warnings (flooding that builds slowly over a wide area)",
    ]:
        assert words in not_scored


def test_the_score_line_lists_the_warnings_it_counts(ctx):
    what = run_tool(ctx, "rank_hubs", rank_args()).display.what_counts
    assert (
        "Warnings counted: winter weather: Winter Storm, Blizzard, Ice Storm, Lake Effect Snow; "
        "flooding: Flash Flood; severe storms: Tornado, Severe Thunderstorm."
    ) in what


def test_the_explanation_says_whose_calendar_years(ctx):
    what = run_tool(ctx, "explain_hub", {"hub_id": "DAL"}).display.what_counts
    assert "Years are calendar years in the hub's own time zone." in what


def test_the_confidence_line_says_what_data_coverage_is(ctx):
    reason = run_tool(ctx, "rank_hubs", rank_args()).provenance.confidence_reason
    assert reason.startswith("Data coverage 100% (the share of the records these figures need that the data holds).")


def test_the_winter_note_names_the_agency_in_full(ctx):
    assert "the Federal Highway Administration's Regional Assessment" in ctx.config.winter_note


def test_the_sources_say_who_runs_them():
    assert SOURCE_NAMES["iem_warning_archive"] == (
        "National Weather Service warnings, from Iowa State University's Iowa Environmental Mesonet archive"
    )
    assert SOURCE_NAMES["noaa_station_acis"] == (
        "NOAA airport station observations, through ACIS, the data service of NOAA's Regional Climate Centers"
    )


RETIRED_TERMS = ["day-equivalent", "qualifying", "local calendar", "FHWA's", "ACIS service"]


@pytest.mark.parametrize(
    "name, args",
    [
        ("list_hubs", {"region": "all"}),
        ("rank_hubs", rank_args()),
        ("rank_hubs", rank_args(hazard="hurricane")),
        ("compare_hubs", {"hub_ids": ["MIA", "IAH"], "hazards": ["overall", "hurricane", "flood"]}),
        ("explain_hub", {"hub_id": "DAL"}),
        ("daily_weather_stats", stats_args()),
        ("daily_weather_stats", stats_args(hub_id="IAH", metric="precipitation")),
        ("get_methodology", {}),
    ],
)
def test_no_tool_text_uses_a_retired_term(ctx, name, args):
    r = run_tool(ctx, name, args)
    d, p = r.display, r.provenance
    text = " ".join([d.title, *d.columns, d.what_counts, *d.notes, p.confidence_reason, *map(SOURCE_NAMES.get, p.sources),
                     json.dumps(r.data)])  # fmt: skip
    assert [t for t in RETIRED_TERMS if t in text] == []


def test_the_snowfall_share_shows_at_the_precision_the_tool_rounds_it(ctx):
    # Review, 2026-11-25: 26 of 364 is 7.14%, so "7.10" claimed a precision the figure does not have.
    from wra.tools.text import display_text

    result = run_tool(ctx, "daily_weather_stats", stats_args())
    assert result.display.rows[-1] == ["Share of observed days (%)", "7.1"]
    assert "7.10" not in display_text(result.display)


def test_a_comparison_over_several_hazards_says_who_leads_each(ctx):
    notes = run_tool(ctx, "compare_hubs", MIA_IAH).display.notes
    assert ("Most exposed first, by hazard. Hurricanes: Miami 1.52, then Houston 0.92. "
            "Flooding: Houston 0.47, then Miami 0.21.") in notes


def test_a_comparison_over_one_hazard_has_no_lead_note(ctx):
    notes = run_tool(ctx, "compare_hubs", {"hub_ids": ["MIA", "IAH"], "hazards": ["flood"]}).display.notes
    assert not any(n.startswith("Most exposed first") for n in notes)
