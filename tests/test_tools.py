"""The tools, on the database built from the committed raw responses, with "today" pinned to 2026-11-24."""

import json
from datetime import date

import pytest

from conftest import REPO
from wra.scoring.config import load_scoring_config
from wra.stored import load_stored
from wra.tools.context import ToolContext
from wra.tools.envelope import ToolResult
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
    assert result.data["rows"][-1]["clear_of_next"] is None


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
