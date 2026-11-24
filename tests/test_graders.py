"""The graders' own tests (plan section 10.3): a hand-written correct answer passes every check,
an empty or wrong one fails.

Tables in the hand-written answers come from the real tools, as the agent's would.
Hub orders and verdicts are typed by hand from the ranking printed by `wra rank`,
so they also check the orders the graders compute.
"""

import dataclasses
from datetime import date

import pytest

from conftest import REPO
from wra.agent.schemas import AgentReply, ToolCallRecord, Trace
from wra.evals.cases import CASES
from wra.evals.graders import case_passed, grade
from wra.scoring.config import load_scoring_config
from wra.stored import load_stored
from wra.tools.context import ToolContext
from wra.tools.registry import run_tool

BY_ID = {c.id: c for c in CASES}
NO_CHANGE = []
HURRICANE_X2 = [{"hazard": "hurricane", "mode": "multiply", "value": 2}]


@pytest.fixture(scope="module")
def ctx(real_db):
    return ToolContext(load_stored(real_db), load_scoring_config(REPO / "config" / "scoring.toml"), date(2026, 11, 24))


def rank(hazard="overall", region="all", top_n=None, changes=NO_CHANGE):
    return ("rank_hubs", {"hazard": hazard, "region": region, "top_n": top_n, "weight_changes": changes})


def snow(start=None, end=None, threshold="measurable"):
    return ("daily_weather_stats", {"hub_id": "DEN", "metric": "snowfall", "start_year": start,
                                    "end_year": end, "threshold": threshold})  # fmt: skip


def reply(ctx, status, verdict, calls=(), hubs=(), what_if=False, show=None, caveats=(), cited=(), orders=()):
    """An answer as the agent would build it: tool calls recorded, their tables shown (or those in `show`).

    `cited` are calls from earlier turns whose tables this answer shows again, without calling anew.
    """
    tables = [run_tool(ctx, name, args).display for name, args in cited]
    records = []
    for n, (name, args) in enumerate(calls):
        records.append(ToolCallRecord(id=f"call_{n}", name=name, input=args))
        result = run_tool(ctx, name, args)
        if result.ok and (show is None or n in show):
            tables.append(result.display)
    return AgentReply(session_id="s", status=status, verdict=verdict, tables=tables, caveats=list(caveats),
                      hubs_ranked=list(hubs), is_what_if=what_if, trace=Trace(model="hand", tool_calls=records),
                      hazard_orders=[{"hazard": h, "hubs": list(o)} for h, o in orders])  # fmt: skip


def correct(ctx, case_id: int) -> list[AgentReply]:
    r = lambda *a, **k: reply(ctx, *a, **k)  # noqa: E731
    setup_overall = r("answered", "Minneapolis leads.", [rank()], ["MSP", "MEM", "DEN"])
    setup_q1 = r("answered", "Minneapolis is most exposed.", [rank("winter", "midwest")], ["MSP", "MCI"])
    setup_q2 = r("answered", "Miami leads on hurricanes, Houston on floods.",
                 [("compare_hubs", {"hub_ids": ["MIA", "IAH"], "hazards": ["hurricane", "flood"]})],
                 orders=[("hurricane", ["MIA", "IAH"]), ("flood", ["IAH", "MIA"])])
    answers = {
        1: [r("answered", "Minneapolis stands clear at the top; Kansas City and Chicago are close behind.",
              [rank("winter", "midwest")], ["MSP", "MCI", "ORD"])],
        2: [setup_q2],
        3: [r("answered", "Denver had measurable snowfall on 7.1% of observed days in 2025 (26 of 364).", [snow()])],
        4: [r("answered", "Dallas is High, but only just: 2.02 against a cut-off of 2.", [("explain_hub", {"hub_id": "DAL"})])],
        5: [setup_q1, r("answered", "Columbus is the least exposed of the Midwest hubs.", [], ["CMH"],
                        cited=[rank("winter", "midwest")])],
        6: [setup_q2, r("answered", "Houston is slightly worse overall, 1.96 against 1.85.",
                        [("compare_hubs", {"hub_ids": ["IAH", "MIA"], "hazards": ["overall"]})], ["IAH", "MIA"])],
        7: [setup_overall, r("answered", "In this what-if Miami moves to the top.", [rank(changes=HURRICANE_X2)],
                             ["MIA", "MSP"], what_if=True)],
        8: [setup_overall, r("answered", "In the what-if Miami led.", [rank(changes=HURRICANE_X2)], ["MIA"], True),
            r("answered", "Back to the official weights: Minneapolis leads.", [rank()], ["MSP", "MEM"])],
        9: [r("answered", "Minneapolis, Memphis and Denver.", [rank(top_n=3)], ["MSP", "MEM", "DEN"])],
        10: [r("answered", "Days under warning, weighted 1 for winter, flood and storms; hurricanes count 5 days "
                           "per event.", [("get_methodology", {})])],
        11: [r("out_of_scope", "We have no Seattle hub.", [("list_hubs", {"region": "all"})])],
        12: [r("out_of_scope", "Forecasts are outside what this tool covers.")],
        13: [r("out_of_scope", "The score covers four hazards; earthquake risk is not one of them.",
               [("get_methodology", {})])],
        14: [r("no_data", "Station data covers 2016 to 2025, so 2010 is not available.", [snow(2010, 2010)])],
    }  # fmt: skip
    return answers[case_id]


@pytest.mark.parametrize("case_id", sorted(BY_ID))
def test_a_correct_answer_passes_every_check(ctx, case_id):
    checks = grade(ctx, BY_ID[case_id], correct(ctx, case_id))
    assert case_passed(checks), [c for c in checks if c.passed is False]
    assert any(c.passed for c in checks)


@pytest.mark.parametrize("case_id", sorted(BY_ID))
def test_an_empty_answer_fails(ctx, case_id):
    empty = AgentReply(session_id="s", status="error", verdict="", trace=Trace(model="stub"))
    assert not case_passed(grade(ctx, BY_ID[case_id], [empty] * len(BY_ID[case_id].turns)))


def failing(ctx, case_id: int, replies: list[AgentReply]) -> set[str]:
    return {c.name for c in grade(ctx, BY_ID[case_id], replies) if c.passed is False}


def test_wrong_status_fails_status(ctx):
    assert failing(ctx, 11, [reply(ctx, "answered", "Seattle is fine.")]) == {"status"}


def test_a_what_if_not_flagged_fails_status(ctx):
    answers = correct(ctx, 7)
    answers[-1] = answers[-1].model_copy(update={"is_what_if": False})
    assert failing(ctx, 7, answers) == {"status"}


def test_a_data_tool_in_an_out_of_scope_answer_fails_tool(ctx):
    answer = reply(ctx, "out_of_scope", "Forecasts are not covered.", [snow(2025, 2025)])
    assert failing(ctx, 12, [answer]) == {"tool"}


def test_the_wrong_year_fails_tool_and_numbers(ctx):
    answer = reply(ctx, "answered", "Denver had snowfall on 7.1% of days.", [snow(2024, 2024)])
    assert failing(ctx, 3, [answer]) == {"tool", "numbers"}


def test_showing_another_calls_table_fails_numbers(ctx):
    # Both calls made, but only the 2024 table shown: the answer is about the wrong year.
    answer = reply(ctx, "answered", "Denver had snowfall on 7.1% of days.", [snow(), snow(2024, 2024)], show={1})
    assert failing(ctx, 3, [answer]) == {"numbers"}


def test_a_pinned_value_the_tool_does_not_give_fails_numbers(ctx):
    # Stands in for a bug in our own tool: the hand-checked 26 days no longer come back.
    bent = dataclasses.replace(BY_ID[3], pinned={"days_meeting": 27})
    assert {c.name for c in grade(ctx, bent, correct(ctx, 3)) if c.passed is False} == {"numbers"}


def test_hubs_in_the_wrong_order_fail_hubs(ctx):
    answer = reply(ctx, "answered", "Minneapolis is second to Kansas City.", [rank("winter", "midwest")], ["MCI", "MSP"])
    assert failing(ctx, 1, [answer]) == {"hubs"}


def test_a_top_three_with_two_hubs_fails_hubs(ctx):
    answer = reply(ctx, "answered", "Minneapolis and Memphis.", [rank(top_n=3)], ["MSP", "MEM"])
    assert failing(ctx, 9, [answer]) == {"hubs"}


def test_the_wrong_least_exposed_hub_fails_hubs(ctx):
    answers = correct(ctx, 5)
    answers[-1] = answers[-1].model_copy(update={"hubs_ranked": ["IND"], "verdict": "Columbus? No, Indianapolis."})
    assert failing(ctx, 5, answers) == {"hubs"}


def test_a_missing_band_fails_mentions(ctx):
    answer = reply(ctx, "answered", "Dallas has a lot of flooding.", [("explain_hub", {"hub_id": "DAL"})])
    assert failing(ctx, 4, [answer]) == {"mentions"}


@pytest.mark.parametrize(
    "verdict",
    [
        "Dallas is rated Very high, at 2.02 days a year.",
        "Dallas is not high: it is Moderate, at 2.02 days a year.",
        "Dallas's risk is high.",  # lowercase: not the band as the tools write it
    ],
)
def test_a_wrong_or_unnamed_band_fails_mentions(ctx, verdict):
    answer = reply(ctx, "answered", verdict, [("explain_hub", {"hub_id": "DAL"})])
    assert failing(ctx, 4, [answer]) == {"mentions"}


def test_a_number_inside_another_number_is_not_a_mention(ctx):
    answer = reply(ctx, "answered", "Denver had measurable snowfall on 17.1% of days.", [snow()])
    assert failing(ctx, 3, [answer]) == {"mentions"}


def test_the_first_run_s_dallas_answer_passes(ctx):
    # Verbatim from the first evaluation run (2026-11-24); it failed the earlier rule that no other band
    # may be named anywhere, because a caveat mentions Moderate.
    answer = reply(ctx, "answered",
                   "Dallas is in the **High** band, but only just: it scores 2.02 expected disruption days a year, "
                   "and High starts at 2. It ranks 6th of 12.", [("explain_hub", {"hub_id": "DAL"})],
                   caveats=["Because Dallas is so close to the 2-day cutoff, one quieter year could drop it to "
                            "Moderate, so don't treat the High label as firm."])  # fmt: skip
    assert failing(ctx, 4, [answer]) == set()


def test_the_first_run_s_methodology_answer_passes_and_without_the_figures_fails(ctx):
    verdict = ("Winter weather, flooding and severe storms each count 1 disruption day for every day the hub was "
               "under a qualifying National Weather Service warning (2016–2025). Hurricanes count **5** disruption "
               "days per event, based on FEMA's long-run hurricane frequency for the hub's county.")  # fmt: skip
    assert failing(ctx, 10, [reply(ctx, "answered", verdict, [("get_methodology", {})])]) == set()
    vague = "Each hazard's time under warning is weighted, and hurricanes count more."
    assert failing(ctx, 10, [reply(ctx, "answered", vague, [("get_methodology", {})])]) == {"mentions"}


def test_weights_written_with_decimals_satisfy_case_10(ctx):
    verdict = "Winter, flood and storms weigh 1.0 per day under warning; hurricanes weigh 5.0 days per event."
    assert failing(ctx, 10, [reply(ctx, "answered", verdict, [("get_methodology", {})])]) == set()


def test_low_confidence_is_not_a_band(ctx):
    answer = reply(ctx, "answered", "Dallas is High, but only just. Low confidence: its neighbours are close.",
                   [("explain_hub", {"hub_id": "DAL"})])  # fmt: skip
    assert failing(ctx, 4, [answer]) == set()


def test_a_dollar_figure_fails_mentions(ctx):
    answers = correct(ctx, 2)
    answers[-1] = answers[-1].model_copy(update={"caveats": ["Upgrading Miami would cost $5 million."]})
    assert failing(ctx, 2, answers) == {"mentions"}


def test_a_follow_up_may_reuse_the_earlier_result(ctx):
    # Case 5's last reply calls no tool; the ranking from the first turn counts.
    checks = {c.name: c for c in grade(ctx, BY_ID[5], correct(ctx, 5))}
    assert correct(ctx, 5)[-1].trace.tool_calls == []
    assert checks["tool"].passed is True and checks["numbers"].passed is True


# --- the target over a whole run (plan section 10.3) ---------------------------------------


def _runs(failed: set[tuple[int, int]], reps: int = 3):
    """Fourteen cases times `reps`, passing except the (case, rep) pairs in `failed`."""
    from wra.evals.run import CaseRun

    return [CaseRun(case.id, rep, (case.id, rep) not in failed, False, 1.0, [], [])
            for case in CASES for rep in range(reps)]  # fmt: skip


def test_the_target_is_met_when_every_case_run_passes():
    from wra.evals.run import target_met

    met, text = target_met(_runs(set()))
    assert met and text.startswith("Target (plan section 10.3): met.")


def test_one_failed_assignment_question_misses_the_target_even_above_90_percent():
    from wra.evals.run import target_met

    met, text = target_met(_runs({(3, 1)}))  # 41 of 42 passed, but the Denver question failed once
    assert not met and "11 of 12 runs" in text


def test_the_target_needs_90_percent_of_all_case_runs():
    from wra.evals.run import target_met

    assert target_met(_runs({(c, 0) for c in (10, 11, 12, 13)}))[0]  # 38 of 42, 90.5%
    assert not target_met(_runs({(c, 0) for c in (9, 10, 11, 12, 13)}))[0]  # 37 of 42, 88.1%


# --- found by the milestone 5 model comparison (owner's fixes, 2026-11-25) -------------------


def test_a_required_word_may_be_plural():
    from wra.evals.graders import _has

    assert _has("We don't score earthquakes.", "earthquake")  # Sonnet's right answer to case 13
    assert not _has("an earthquakeproof site", "earthquake")


def test_neither_hub_clearly_worse_passes_the_overall_follow_up(ctx):
    # Case 6's follow-up: Houston 1.96, Miami 1.85, a gap within the year-to-year swings. Saying neither is
    # clearly worse, with no order asserted, is a right answer (Sonnet, milestone 5 comparison).
    turns = correct(ctx, 6)
    neither = turns[-1].model_copy(update={"verdict": "Neither hub is clearly worse overall: Houston scores 1.96 "
                                   "and Miami 1.85, a gap within the year-to-year swings.", "hubs_ranked": []})  # fmt: skip
    checks = {c.name: c for c in grade(ctx, BY_ID[6], [turns[0], neither])}
    assert checks["hubs"].passed is True, checks["hubs"].detail


@pytest.mark.parametrize(
    "verdict, hubs",
    [("Houston is worse overall, 1.96 against 1.85.", []), ("Neither is clearly worse; Miami is worse.", ["MIA", "IAH"])],
)
def test_no_order_without_saying_so_or_a_wrong_order_still_fails(ctx, verdict, hubs):
    turns = correct(ctx, 6)
    answer = turns[-1].model_copy(update={"verdict": verdict, "hubs_ranked": hubs})
    checks = {c.name: c for c in grade(ctx, BY_ID[6], [turns[0], answer])}
    assert checks["hubs"].passed is False


def test_the_comparison_checks_the_answers_order_for_each_hazard(ctx):
    right = correct(ctx, 2)
    swapped = AgentReply.model_validate({**right[0].model_dump(), "hazard_orders": [
        {"hazard": "hurricane", "hubs": ["IAH", "MIA"]}, {"hazard": "flood", "hubs": ["MIA", "IAH"]}]})  # fmt: skip
    missing = right[0].model_copy(update={"hazard_orders": []})
    assert {c.name: c for c in grade(ctx, BY_ID[2], right)}["hubs"].passed is True
    check = {c.name: c for c in grade(ctx, BY_ID[2], [swapped])}["hubs"]
    assert check.passed is False and "hurricane" in check.detail
    assert {c.name: c for c in grade(ctx, BY_ID[2], [missing])}["hubs"].passed is False
