"""The agent loop against a scripted fake model: no network, no cost (plan section 13, milestone 3 check)."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from conftest import REPO
from wra.agent.loop import ClaudeAgent
from wra.agent.settings import load_settings
from wra.scoring.config import load_scoring_config
from wra.stored import load_stored
from wra.tools.context import ToolContext
from wra.tools.registry import run_tool

WINTER_MIDWEST = {"hazard": "winter", "region": "midwest", "top_n": None, "weight_changes": []}


@pytest.fixture(scope="module")
def ctx(real_db):
    return ToolContext(load_stored(real_db), load_scoring_config(REPO / "config" / "scoring.toml"), date(2026, 11, 24))


class Scripted:
    """Returns the scripted responses in order and keeps every request it was sent."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def create(self, **request):
        self.requests.append({**request, "messages": list(request["messages"])})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def response(stop_reason, *blocks):
    usage = SimpleNamespace(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks), usage=usage, model="claude-opus-5-5")


def tool(name, args, call_id="toolu_1"):
    return response("tool_use", SimpleNamespace(type="thinking", thinking=""),
                    SimpleNamespace(type="tool_use", id=call_id, name=name, input=args))  # fmt: skip


def final(verdict="Minneapolis is clearly the most exposed, at 2.71 days a year.", evidence=("R1",),
          hubs=("MSP", "MCI"), status="answered", what_if=False, caveats=()):  # fmt: skip
    body = {"status": status, "verdict": verdict, "evidence": list(evidence), "hubs_ranked": list(hubs),
            "is_what_if": what_if, "caveats": list(caveats)}  # fmt: skip
    return response("end_turn", SimpleNamespace(type="text", text=json.dumps(body)))


def agent(ctx, *responses):
    client = Scripted(*responses)
    return ClaudeAgent(ctx, load_settings(REPO / "config" / "agent.toml"), client), client


# --- the five scenarios of the milestone 3 check -------------------------------------------


def test_a_valid_answer_is_shown_with_the_tables_and_footnote_from_code(ctx):
    a, client = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), final())
    reply = a.answer(None, "Which hubs in the Midwest are most exposed to winter disruption?")
    assert reply.status == "answered" and not reply.trace.repaired
    assert reply.tables == [run_tool(ctx, "rank_hubs", WINTER_MIDWEST).display]
    assert reply.footnote.confidence == "low" and "Minneapolis above Kansas City" in reply.footnote.confidence_reason
    assert [(c.id, c.name) for c in reply.trace.tool_calls] == [("R1", "rank_hubs")]
    assert reply.trace.usage["input_tokens"] == 200 and reply.trace.usage["output_tokens"] == 100
    sent = client.requests[1]["messages"][-1]["content"][0]
    assert sent["tool_use_id"] == "toolu_1" and json.loads(sent["content"])["result_id"] == "R1"


def test_an_invalid_answer_gets_one_repair(ctx):
    a, client = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), final(evidence=["R9"]), final())
    reply = a.answer(None, "Which hubs in the Midwest are most exposed to winter disruption?")
    assert reply.status == "answered" and reply.trace.repaired
    repair = client.requests[2]["messages"][-1]
    assert repair["role"] == "user" and "R9" in repair["content"]


def test_an_answer_invalid_twice_gives_a_clear_error(ctx):
    a, _ = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), final(evidence=["R9"]), final(evidence=["R9"]))
    reply = a.answer(None, "Which hubs in the Midwest are most exposed to winter disruption?")
    assert reply.status == "error" and "failed validation twice" in reply.error
    assert reply.verdict == "" and reply.tables == []


def test_an_ungrounded_number_triggers_a_repair(ctx):
    planted = final(verdict="Minneapolis leads at 3.71 days a year.")
    a, client = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), planted, final())
    reply = a.answer(None, "Which hubs in the Midwest are most exposed to winter disruption?")
    assert reply.status == "answered" and reply.trace.repaired
    assert "3.71" in client.requests[2]["messages"][-1]["content"]


def test_a_declined_reply_is_an_error(ctx):
    a, _ = agent(ctx, response("refusal"))
    reply = a.answer(None, "Which hubs are most exposed?")
    assert reply.status == "error" and "declined" in reply.error


# --- more ways an answer can go wrong ------------------------------------------------------


def test_a_reply_cut_off_at_the_token_limit_is_an_error(ctx):
    a, _ = agent(ctx, response("max_tokens", SimpleNamespace(type="text", text='{"status": "ans')))
    assert "cut off" in a.answer(None, "Which hubs are most exposed?").error


def test_text_that_is_not_an_answer_object_is_repaired(ctx):
    a, client = agent(ctx, tool("rank_hubs", WINTER_MIDWEST),
                      response("end_turn", SimpleNamespace(type="text", text="not json")), final())  # fmt: skip
    assert a.answer(None, "Which hubs in the Midwest are most exposed?").trace.repaired
    assert "not a valid answer object" in client.requests[2]["messages"][-1]["content"]


def test_hubs_out_of_the_cited_order_are_repaired(ctx):
    a, client = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), final(hubs=["MCI", "MSP"]), final())
    assert a.answer(None, "Which hubs in the Midwest are most exposed?").trace.repaired
    assert "does not follow the order" in client.requests[2]["messages"][-1]["content"]


def test_a_what_if_must_be_flagged(ctx):
    what_if = {**WINTER_MIDWEST, "hazard": "overall", "region": "all",
               "weight_changes": [{"hazard": "hurricane", "mode": "multiply", "value": 2}]}  # fmt: skip
    a, client = agent(ctx, tool("rank_hubs", what_if), final(verdict="Miami leads.", hubs=["MIA"]),
                      final(verdict="In this what-if Miami leads.", hubs=["MIA"], what_if=True))  # fmt: skip
    reply = a.answer(None, "What if a hurricane counted double?")
    assert reply.trace.repaired and reply.is_what_if
    assert "is_what_if is False" in client.requests[2]["messages"][-1]["content"]


def test_the_model_call_limit_ends_in_an_error(ctx):
    a, _ = agent(ctx, *[tool("list_hubs", {"region": "all"}, f"toolu_{n}") for n in range(6)])
    reply = a.answer(None, "Which hubs are there?")
    assert reply.status == "error" and "6 model calls" in reply.error


def test_an_api_failure_is_an_error_naming_only_its_kind(ctx):
    a, _ = agent(ctx, ConnectionError("secret request details"))
    reply = a.answer(None, "Which hubs are most exposed?")
    assert reply.status == "error" and "ConnectionError" in reply.error and "secret" not in reply.error


# --- conversations and the no-data case ----------------------------------------------------


def test_a_follow_up_can_cite_a_result_from_an_earlier_turn(ctx):
    a, _ = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), final(),
                 final(verdict="Columbus is the least exposed.", hubs=["CMH"]))  # fmt: skip
    first = a.answer(None, "Which hubs in the Midwest are most exposed to winter disruption?")
    second = a.answer(first.session_id, "And which is the least exposed?")
    assert second.status == "answered" and second.session_id == first.session_id
    assert second.trace.tool_calls == [] and second.tables == first.tables


def test_no_data_cites_the_tools_refusal_and_shows_no_table(ctx):
    args = {"hub_id": "DEN", "metric": "snowfall", "start_year": 2010, "end_year": 2010, "threshold": "measurable"}
    a, _ = agent(ctx, tool("daily_weather_stats", args),
                 final(verdict="Station data covers 2016 to 2025, so 2010 is not available.", hubs=[],
                       status="no_data"))  # fmt: skip
    reply = a.answer(None, "What percentage of days in Denver had snowfall in 2010?")
    assert reply.status == "no_data" and reply.tables == [] and reply.footnote is None


# --- what is sent ---------------------------------------------------------------------------


def test_the_request_uses_strict_tools_and_the_answer_schema_and_never_forces_a_tool(ctx):
    a, client = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), final())
    a.answer(None, "Which hubs in the Midwest are most exposed?")
    first, second = client.requests
    tools = {t["name"]: t for t in first["tools"]}
    assert sorted(tools) == sorted(["list_hubs", "rank_hubs", "compare_hubs", "explain_hub", "daily_weather_stats",
                                    "get_methodology"])  # fmt: skip
    assert all(t["strict"] for t in tools.values())
    explain = tools["explain_hub"]["input_schema"]
    assert explain["properties"]["hub_id"]["enum"] == list(ctx.data.hubs)
    assert explain["additionalProperties"] is False and explain["required"] == ["hub_id"]
    sent = json.dumps(first["tools"])
    assert all(word not in sent for word in ('"minimum"', '"minItems"', '"maxItems"', '"pattern"', '"title"'))
    schema = first["output_config"]["format"]["schema"]
    assert schema["properties"]["status"]["enum"] == ["answered", "out_of_scope", "no_data", "needs_clarification"]
    assert first["output_config"]["effort"] == "medium" and first["model"] == "claude-opus-5-5"
    assert first["fallbacks"] == "default" and first["betas"] == ["server-side-fallback-2026-07-01"]
    assert "tool_choice" not in first and "temperature" not in first
    assert first["system"] == second["system"] and first["tools"] == second["tools"]
