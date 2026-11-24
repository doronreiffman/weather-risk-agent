"""The API step of the final end-to-end check (plan section 13, steps 4 and 5), run here through FastAPI's
test client on the scripted fake model: no network, no cost. The real run is scripts/e2e.sh."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from conftest import REPO
from test_agent_loop import WINTER_MIDWEST, Scripted, final, tool
from wra.agent.loop import ClaudeAgent
from wra.agent.settings import load_settings
from wra.api.app import create_app
from wra.evals.e2e import QUESTIONS, check, least_exposed_midwest_winter
from wra.scoring.config import load_scoring_config
from wra.stored import load_stored
from wra.tools.context import ToolContext

FOLLOW_UP = final(verdict="Columbus is the least exposed.", hubs=["CMH"], hubs_from="bottom")
SEATTLE = final(status="out_of_scope", verdict="There is no Seattle hub.", evidence=(), hubs=())


@pytest.fixture(scope="module")
def ctx(real_db):
    return ToolContext(load_stored(real_db), load_scoring_config(REPO / "config" / "scoring.toml"), date(2026, 11, 24))


def served(ctx, *responses):
    agent = ClaudeAgent(ctx, load_settings(REPO / "config" / "agent.toml"), Scripted(*responses))
    return TestClient(create_app(agent, ctx))


def answered():
    return [tool("rank_hubs", WINTER_MIDWEST), final()]


def test_the_six_questions_are_the_assignments_four_a_follow_up_and_one_out_of_scope():
    assert [q.status for q in QUESTIONS] == ["answered"] * 5 + ["out_of_scope"]
    assert [q.follows for q in QUESTIONS] == [False, True, False, False, False, False]
    assert "Seattle" in QUESTIONS[-1].text


def test_the_follow_ups_expected_hub_comes_from_the_scoring_code(ctx):
    assert least_exposed_midwest_winter(ctx) == "CMH"


def test_six_right_replies_pass(ctx):
    http = served(ctx, *answered(), FOLLOW_UP, *answered(), *answered(), *answered(), SEATTLE)
    lines, ok = check(http, "CMH")
    assert ok, lines
    assert lines[-1].startswith("API questions: 6 of 6 passed.")


def test_a_follow_up_that_lost_the_context_and_a_wrong_status_fail(ctx):
    # The follow-up names the top of the ranking, not its bottom; the Seattle question comes back answered.
    lost = final(hubs=("MSP", "MCI"))
    http = served(ctx, *answered(), lost, *answered(), *answered(), *answered(), *answered())
    lines, ok = check(http, "CMH")
    assert not ok
    failed = [line for line in lines if line.startswith("FAIL")]
    assert len(failed) == 2
    assert "does not name CMH" in failed[0] and "status answered, expected out_of_scope" in failed[1]
    assert lines[-1].startswith("API questions: 4 of 6 passed.")
