"""The agent's two limits for the public site (docs/DEPLOY_DESIGN.md 5.3 and 5.4): questions a day, and
conversations held. On the scripted fake model: no network, no cost."""

import dataclasses
from datetime import date

import pytest

from conftest import REPO
from test_agent_loop import WINTER_MIDWEST, Scripted, final, tool
from wra.agent.limits import DailyLimit
from wra.agent.loop import ClaudeAgent
from wra.agent.settings import load_settings
from wra.scoring.config import load_scoring_config
from wra.stored import load_stored
from wra.tools.context import ToolContext

QUESTION = "Which hubs in the Midwest are most exposed to winter disruption?"
FOLLOW_UP = final(verdict="Columbus is the least exposed.", hubs=["CMH"], hubs_from="bottom")


@pytest.fixture(scope="module")
def ctx(real_db):
    return ToolContext(load_stored(real_db), load_scoring_config(REPO / "config" / "scoring.toml"), date(2026, 11, 24))


def settings(**changes):
    return dataclasses.replace(load_settings(REPO / "config" / "agent.toml"), **changes)


# --- the daily limit ---------------------------------------------------------------------------


def test_the_daily_limit_admits_up_to_its_limit_then_refuses():
    limit = DailyLimit(2, today=lambda: date(2026, 11, 25))
    assert [limit.admit(), limit.admit(), limit.admit()] == [True, True, False]


def test_the_daily_limit_starts_again_on_a_new_utc_day():
    day = [date(2026, 11, 25)]
    limit = DailyLimit(1, today=lambda: day[0])
    assert [limit.admit(), limit.admit()] == [True, False]
    day[0] = date(2026, 11, 26)
    assert limit.admit() is True


def test_a_question_over_the_limit_gets_daily_limit_and_reaches_no_model(ctx):
    model = Scripted()
    agent = ClaudeAgent(ctx, settings(), model, admit=lambda: False)
    reply = agent.answer(None, QUESTION)
    assert reply.status == "error" and reply.error_code == "daily_limit"
    assert "midnight UTC" in reply.error
    assert model.requests == []
    # a new conversation's refusal still names a conversation the agent holds, so the page's next question
    # (it keeps the id an error reply carries) continues it instead of meeting a 404
    assert reply.session_id in agent.sessions


def test_refusals_before_answering_do_not_use_the_daily_count(ctx):
    calls = []
    agent = ClaudeAgent(ctx, settings(), Scripted(tool("rank_hubs", WINTER_MIDWEST), final()),
                        admit=lambda: calls.append(1) or True)  # fmt: skip
    first = agent.answer(None, QUESTION)
    assert first.status == "answered" and len(calls) == 1

    assert agent.answer("not-held", "And which is the least exposed?").error_code == "unknown_conversation"
    session = agent.sessions[first.session_id]
    session.busy.acquire()
    try:
        assert agent.answer(first.session_id, "And which is the least exposed?").error_code == "busy"
    finally:
        session.busy.release()
    assert len(calls) == 1


# --- conversations held ------------------------------------------------------------------------


def test_the_least_recently_used_conversation_is_dropped_past_the_cap(ctx):
    model = Scripted(tool("rank_hubs", WINTER_MIDWEST), final(),  # A
                     tool("rank_hubs", WINTER_MIDWEST), final(),  # B
                     FOLLOW_UP,  # A again, so B is now the least recently used
                     tool("rank_hubs", WINTER_MIDWEST), final())  # C, past the cap of two  # fmt: skip
    agent = ClaudeAgent(ctx, settings(max_conversations=2), model)
    a = agent.answer(None, QUESTION).session_id
    b = agent.answer(None, QUESTION).session_id
    assert agent.answer(a, "And which is the least exposed?").status == "answered"
    c = agent.answer(None, QUESTION).session_id

    assert set(agent.sessions) == {a, c}
    sent = len(model.requests)
    assert agent.answer(b, "And which is the least exposed?").error_code == "unknown_conversation"
    assert len(model.requests) == sent
