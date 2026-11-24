"""The agent loop against a scripted fake model: no network, no cost (plan section 13, milestone 3 check)."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from conftest import REPO
from wra.agent.loop import ClaudeAgent
from wra.agent.prompt import system_prompt
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


def response(stop_reason, *blocks, model="claude-opus-5-5"):
    usage = SimpleNamespace(input_tokens=100, output_tokens=50, cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks), usage=usage, model=model)


def tool(name, args, call_id="toolu_1"):
    return response("tool_use", SimpleNamespace(type="thinking", thinking=""),
                    SimpleNamespace(type="tool_use", id=call_id, name=name, input=args))  # fmt: skip


def final(verdict="Minneapolis is clearly the most exposed, at 2.71 days a year.", evidence=("R1",),
          hubs=("MSP", "MCI"), status="answered", what_if=False, caveats=(), hubs_from="top"):  # fmt: skip
    body = {"status": status, "verdict": verdict, "evidence": list(evidence), "hubs_ranked": list(hubs),
            "hubs_from": hubs_from, "is_what_if": what_if, "caveats": list(caveats)}  # fmt: skip
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
    assert any("R9" in p for p in reply.trace.repair_problems)


def test_an_answer_invalid_twice_gives_a_clear_error(ctx):
    a, _ = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), final(evidence=["R9"]), final(evidence=["R9"]))
    reply = a.answer(None, "Which hubs in the Midwest are most exposed to winter disruption?")
    assert reply.status == "error" and "failed validation twice" in reply.error
    assert reply.error_code == "invalid_twice"
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
    assert reply.status == "error" and "declined" in reply.error and reply.error_code == "declined"


# --- more ways an answer can go wrong ------------------------------------------------------


def test_a_reply_cut_off_at_the_token_limit_is_an_error(ctx):
    a, _ = agent(ctx, response("max_tokens", SimpleNamespace(type="text", text='{"status": "ans')))
    reply = a.answer(None, "Which hubs are most exposed?")
    assert "cut off" in reply.error and reply.error_code == "cut_off"


def test_text_that_is_not_an_answer_object_is_repaired(ctx):
    a, client = agent(ctx, tool("rank_hubs", WINTER_MIDWEST),
                      response("end_turn", SimpleNamespace(type="text", text="not json")), final())  # fmt: skip
    assert a.answer(None, "Which hubs in the Midwest are most exposed?").trace.repaired
    assert "not a valid answer object" in client.requests[2]["messages"][-1]["content"]


def test_hubs_out_of_the_cited_order_are_repaired(ctx):
    a, client = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), final(hubs=["MCI", "MSP"]), final())
    assert a.answer(None, "Which hubs in the Midwest are most exposed?").trace.repaired
    assert "is not the top of any cited order" in client.requests[2]["messages"][-1]["content"]


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
    assert reply.status == "error" and "6 model calls" in reply.error and reply.error_code == "too_many_calls"


def test_an_api_failure_is_an_error_naming_only_its_kind(ctx):
    a, client = agent(ctx, ConnectionError("secret request details"))
    reply = a.answer(None, "Which hubs are most exposed?")
    assert reply.status == "error" and "ConnectionError" in reply.error and "secret" not in reply.error
    assert reply.error_code == "model_call_failed" and len(client.requests) == 1  # not an SDK error: no retry


# --- conversations and the no-data case ----------------------------------------------------


def test_a_follow_up_can_cite_a_result_from_an_earlier_turn(ctx):
    a, _ = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), final(),
                 final(verdict="Columbus is the least exposed.", hubs=["CMH"], hubs_from="bottom"))  # fmt: skip
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
    # The owner's choice after the milestone 5 comparison: Haiku 5.5, which has no server-side refusal fallback.
    assert first["output_config"]["effort"] == "medium" and first["model"] == "claude-haiku-5-5"
    assert "fallbacks" not in first and "betas" not in first
    assert "tool_choice" not in first and "temperature" not in first
    assert first["system"] == second["system"] and first["tools"] == second["tools"]


def test_the_refusal_fallback_is_sent_when_configured(ctx):
    import dataclasses

    settings = dataclasses.replace(load_settings(REPO / "config" / "agent.toml"), model="claude-opus-5-5",
                                   fallbacks="default")  # fmt: skip
    client = Scripted(final())
    ClaudeAgent(ctx, settings, client).answer(None, "Which hubs in the Midwest are most exposed?")
    assert client.requests[0]["fallbacks"] == "default"
    assert client.requests[0]["betas"] == ["server-side-fallback-2026-07-01"]


# --- the owner's additions after the milestone 3 review --------------------------------------


def repaired_because(ctx, first, *, calls=(tool("rank_hubs", WINTER_MIDWEST),), question="Which hubs?"):
    """Run a script whose first final answer is `first`, followed by a valid one; return the repair reasons."""
    a, _ = agent(ctx, *calls, first, final())
    reply = a.answer(None, question)
    assert reply.status == "answered"
    return " ".join(reply.trace.repair_problems)


def test_the_wrong_end_of_the_ranking_is_repaired(ctx):
    assert "top of any cited order" in repaired_because(
        ctx, final(verdict="Columbus is the most exposed Midwest hub.", hubs=["CMH"]))
    assert "top of any cited order" in repaired_because(
        ctx, final(verdict="The two most exposed are Minneapolis and Columbus.", hubs=["MSP", "CMH"]))


def test_a_wrong_band_word_is_repaired(ctx):
    explain = tool("explain_hub", {"hub_id": "DAL"})
    wrong = final(verdict="Dallas is in the Very high band at 2.02.", hubs=[])
    a, client = agent(ctx, explain, wrong, final(verdict="Dallas is High, at 2.02.", hubs=[]))
    reply = a.answer(None, "Why is the Dallas hub's risk high?")
    assert reply.status == "answered" and "cited band is 'High'" in reply.trace.repair_problems[0]
    assert reply.trace.rejected_answer and "Very high" in reply.trace.rejected_answer


@pytest.mark.parametrize(
    "verdict",
    [
        "No hub is Very high; Minneapolis comes closest.",
        "Dallas is High, just above Moderate, at 2.02.",
        "Chicago (2.03) is just above Dallas, which is High.",
    ],
)
def test_band_words_are_paired_with_the_hub_just_before_them(ctx, verdict):
    a, _ = agent(ctx, tool("explain_hub", {"hub_id": "DAL"}), final(verdict=verdict, hubs=[]))
    reply = a.answer(None, "Why is Dallas high?")
    assert reply.status == "answered" and not reply.trace.repaired, reply.trace.repair_problems


OFFICIAL_OVERALL = {"hazard": "overall", "region": "all", "top_n": None, "weight_changes": []}
WHAT_IF_OVERALL = {**OFFICIAL_OVERALL, "weight_changes": [{"hazard": "hurricane", "mode": "multiply", "value": 2}]}


def test_a_what_if_answer_that_also_cites_the_official_ranking_may_name_the_what_if_band(ctx):
    # Haiku, milestone 5 comparison: it cited the what-if (Miami Very high) and the official ranking (Miami
    # Moderate), and the check compared its band with the last one cited only, refusing a right answer.
    right = final(verdict="In this what-if Miami moves to first at 3.37 days a year, in the Very high band.",
                  evidence=("R2", "R1"), hubs=("MIA",), what_if=True)  # fmt: skip
    a, _ = agent(ctx, tool("rank_hubs", OFFICIAL_OVERALL), tool("rank_hubs", WHAT_IF_OVERALL, "toolu_2"), right)
    reply = a.answer(None, "Which hubs are most exposed overall, and what if a hurricane counted double?")
    assert reply.status == "answered" and not reply.trace.repaired, reply.trace.repair_problems


def test_a_band_that_no_cited_ranking_gives_is_still_repaired(ctx):
    wrong = final(verdict="In this what-if Miami moves to first, in the High band.", evidence=("R2", "R1"),
                  hubs=("MIA",), what_if=True)  # fmt: skip
    right = final(verdict="In this what-if Miami moves to first, in the Very high band.", evidence=("R2", "R1"),
                  hubs=("MIA",), what_if=True)  # fmt: skip
    a, _ = agent(ctx, tool("rank_hubs", OFFICIAL_OVERALL), tool("rank_hubs", WHAT_IF_OVERALL, "toolu_2"), wrong, right)
    reply = a.answer(None, "What if a hurricane counted double?")
    assert reply.status == "answered" and reply.trace.repaired
    assert "calls Miami 'High'" in reply.trace.repair_problems[0]


def test_the_prompts_own_facts_need_no_citation(ctx):
    answer = final(status="out_of_scope", evidence=[], hubs=[],
                   verdict="We have no Seattle hub; our data covers 2016 to 2025 at our 12 hubs.")  # fmt: skip
    a, _ = agent(ctx, answer)
    reply = a.answer(None, "How exposed is our Seattle hub?")
    assert reply.status == "out_of_scope" and not reply.trace.repaired


def test_a_table_in_the_verdict_or_too_many_caveats_is_repaired(ctx):
    table = final(verdict="| Hub | Days |\n|---|---|\n| MSP | 2.71 |")
    assert "contains a table" in repaired_because(ctx, table)
    assert "4 caveats" in repaired_because(ctx, final(caveats=["One.", "Two.", "Three.", "Four."]))


def test_answered_must_cite_a_result_that_succeeded(ctx):
    args = {"hub_id": "DEN", "metric": "snowfall", "start_year": 2010, "end_year": 2010, "threshold": "measurable"}
    first = final(verdict="Station data covers 2016 to 2025.", hubs=[])
    a, _ = agent(ctx, tool("daily_weather_stats", args), first,
                 final(verdict="Station data covers 2016 to 2025.", hubs=[], status="no_data"))  # fmt: skip
    reply = a.answer(None, "Snow in Denver in 2010?")
    assert reply.status == "no_data" and "no cited result succeeded" in reply.trace.repair_problems[0]


def test_several_tool_calls_in_one_response_each_get_a_result(ctx):
    two = response("tool_use",
                   SimpleNamespace(type="tool_use", id="toolu_a", name="rank_hubs", input=WINTER_MIDWEST),
                   SimpleNamespace(type="tool_use", id="toolu_b", name="explain_hub", input={"hub_id": "MSP"}))  # fmt: skip
    a, client = agent(ctx, two, final(evidence=["R1", "R2"]))
    reply = a.answer(None, "Which Midwest hub is most exposed to winter, and why?")
    results = client.requests[1]["messages"][-1]["content"]
    assert [(r["tool_use_id"], json.loads(r["content"])["result_id"]) for r in results] == [("toolu_a", "R1"),
                                                                                           ("toolu_b", "R2")]
    assert reply.status == "answered" and len(reply.tables) == 2 and reply.evidence == ["R1", "R2"]


def test_a_tool_that_raises_becomes_an_error_result(ctx, monkeypatch):
    import wra.agent.loop as loop

    def broken(*args, **kwargs):
        raise RuntimeError("bug")

    monkeypatch.setattr(loop, "run_tool", broken)
    a, client = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), final())
    a.answer(None, "Which hubs?")
    sent = client.requests[1]["messages"][-1]["content"][0]
    assert sent["is_error"] and json.loads(sent["content"])["error"]["code"] == "tool_failed"


def test_a_failed_turn_leaves_no_trace_for_the_next_question(ctx):
    a, client = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), response("refusal"),
                      tool("rank_hubs", WINTER_MIDWEST, "toolu_2"), final())  # fmt: skip
    first = a.answer(None, "Which hubs in the Midwest are most exposed?")
    assert first.status == "error"
    second = a.answer(first.session_id, "Which hubs in the Midwest are most exposed to winter?")
    assert second.status == "answered" and second.evidence == ["R1"]
    assert [m["role"] for m in client.requests[2]["messages"]] == ["user"]


def test_after_a_fallback_the_blocks_before_it_are_left_out_and_not_run(ctx):
    cut = SimpleNamespace(type="tool_use", id="toolu_cut", name="explain_hub", input={"hub_id": "DAL"})
    boundary = SimpleNamespace(type="fallback")
    served = response("tool_use", SimpleNamespace(type="thinking", thinking=""), cut, boundary,
                      SimpleNamespace(type="tool_use", id="toolu_ok", name="rank_hubs", input=WINTER_MIDWEST),
                      model="claude-opus-4-8")  # fmt: skip
    a, client = agent(ctx, served, final())
    reply = a.answer(None, "Which hubs in the Midwest are most exposed?")
    echoed = client.requests[1]["messages"][1]["content"]
    assert [b.type for b in echoed] == ["fallback", "tool_use"] and echoed[1].id == "toolu_ok"
    assert [c.name for c in reply.trace.tool_calls] == ["rank_hubs"]


def test_cost_is_priced_per_response_at_its_own_model(ctx):
    served_by_sonnet = final()
    served_by_sonnet.model = "claude-sonnet-5-5"
    a, _ = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), served_by_sonnet)
    reply = a.answer(None, "Which hubs?")
    # 100 input and 50 output tokens each: once at Opus 5.5's 4 and 20, once at Sonnet 5.5's 2 and 10 per million.
    assert reply.trace.usage["cost_usd"] == round(((100 * 4 + 50 * 20) + (100 * 2 + 50 * 10)) / 1e6, 6)


def test_the_bottom_of_a_cut_ranking_is_not_the_least_exposed(ctx):
    top3 = {"hazard": "overall", "region": "all", "top_n": 3, "weight_changes": []}
    wrong = final(verdict="Denver is the least exposed hub.", hubs=["DEN"], hubs_from="bottom")
    a, _ = agent(ctx, tool("rank_hubs", top3), wrong, final(verdict="Minneapolis leads.", hubs=["MSP"]))
    reply = a.answer(None, "Which hub is least exposed?")
    assert reply.status == "answered" and "not the bottom of any cited order" in reply.trace.repair_problems[0]


def test_an_explanations_order_must_include_the_explained_hub(ctx):
    wrong = final(verdict="Chicago is the most exposed.", hubs=["ORD"])
    a, _ = agent(ctx, tool("explain_hub", {"hub_id": "DAL"}), wrong,
                 final(verdict="Dallas is High, just below Chicago.", hubs=["ORD", "DAL"]))  # fmt: skip
    reply = a.answer(None, "Why is Dallas high?")
    assert reply.status == "answered" and "not the top of any cited order" in reply.trace.repair_problems[0]


# --- milestone 4 readiness: timeouts and two messages at once --------------------------------


def test_the_real_client_uses_the_configured_timeout_and_leaves_retries_to_the_loop(monkeypatch):
    import anthropic
    import dotenv

    from wra.agent.loop import AnthropicClient

    made = {}
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: None)  # no .env is read in tests
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: made.update(kwargs))
    AnthropicClient(load_settings(REPO / "config" / "agent.toml"))
    assert made == {"timeout": 60.0, "max_retries": 0}  # the loop makes the one retry, within the message's time


def _env_file_read(monkeypatch) -> list:
    import anthropic
    import dotenv

    from wra.agent.loop import AnthropicClient

    read = []
    monkeypatch.setattr(dotenv, "load_dotenv", lambda path, *a, **k: read.append(path))  # records, reads nothing
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: None)
    AnthropicClient(load_settings(REPO / "config" / "agent.toml"))
    return read


def test_the_key_file_is_the_projects_dot_env_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("WRA_ENV_FILE", raising=False)
    monkeypatch.setenv("WRA_ROOT", str(tmp_path))
    assert _env_file_read(monkeypatch) == [tmp_path / ".env"]


def test_wra_env_file_points_a_fresh_clone_at_another_key_file(monkeypatch, tmp_path):
    # The end-to-end script's clone has no .env; it names the original's instead of copying it (plan section 13).
    monkeypatch.setenv("WRA_ROOT", str(tmp_path / "clone"))
    monkeypatch.setenv("WRA_ENV_FILE", str(tmp_path / "original" / ".env"))
    assert _env_file_read(monkeypatch) == [tmp_path / "original" / ".env"]


def test_a_second_message_while_the_first_is_answered_is_refused(ctx):
    import threading

    started, release = threading.Event(), threading.Event()

    class Slow(Scripted):
        def create(self, **request):
            started.set()
            release.wait(5)
            return super().create(**request)

    client = Slow(tool("rank_hubs", WINTER_MIDWEST), final())
    a = ClaudeAgent(ctx, load_settings(REPO / "config" / "agent.toml"), client)
    replies = {}
    first = threading.Thread(target=lambda: replies.update(first=a.answer(None, "Which hubs?")))
    first.start()
    started.wait(5)
    (session_id,) = a.sessions
    replies["second"] = a.answer(session_id, "Which hubs, again?")
    release.set()
    first.join(5)
    assert replies["second"].status == "error" and "still being answered" in replies["second"].error
    assert replies["second"].error_code == "busy"
    assert replies["first"].status == "answered"
    assert [m["role"] for m in a.sessions[session_id].messages] == ["user", "assistant", "user", "assistant"]


# --- milestone 4: unknown conversations and the time limit per message -----------------------


def test_an_unknown_conversation_is_refused_without_a_model_call(ctx):
    a, client = agent(ctx, final())
    reply = a.answer("from-before-a-restart", "And which is the least exposed?")
    assert reply.status == "error" and reply.error_code == "unknown_conversation"
    assert reply.session_id == "from-before-a-restart" and "no longer on the server" in reply.error
    assert client.requests == [] and a.sessions == {}


class Clock:
    """Stands in for the loop's time module: calls on the fake model move it on, sleeps are recorded."""

    def __init__(self):
        self.now, self.slept = 0.0, []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    import wra.agent.loop

    fake = Clock()
    monkeypatch.setattr(wra.agent.loop, "time", fake)
    return fake


class Timed(Scripted):
    """Each call takes the given number of seconds on the fake clock. Like a real client it gives up at its
    timeout: a call scripted to take longer raises a timeout then, and its response stays for the retry."""

    def __init__(self, clock, seconds, *responses):
        super().__init__(*responses)
        self.clock, self.seconds = clock, list(seconds)

    def create(self, **request):
        seconds = self.seconds.pop(0)
        if seconds > request["timeout"]:
            self.clock.now += request["timeout"]
            self.requests.append({**request, "messages": list(request["messages"])})
            raise timeout_error()
        self.clock.now += seconds
        return super().create(**request)


def timed(ctx, clock, seconds, *responses):
    client = Timed(clock, seconds, *responses)
    return ClaudeAgent(ctx, load_settings(REPO / "config" / "agent.toml"), client), client


def _request():
    import httpx2

    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def timeout_error():
    import anthropic

    return anthropic.APITimeoutError(request=_request())


def rate_limited(retry_after):
    import anthropic
    import httpx2

    reply = httpx2.Response(429, headers={"retry-after": retry_after}, request=_request())
    return anthropic.RateLimitError("rate limited", response=reply, body=None)


def test_each_call_waits_at_most_the_time_left_in_the_message(ctx, clock):
    a, client = timed(ctx, clock, [50, 5], tool("rank_hubs", WINTER_MIDWEST), final())
    assert a.answer(None, "Which hubs in the Midwest are most exposed?").status == "answered"
    assert [r["timeout"] for r in client.requests] == [60, 40]  # 60 s per call, but only 40 s of the 90 were left


def assert_time_limit(a, reply):
    assert reply.status == "error" and reply.error_code == "time_limit" and "90-second limit" in reply.error
    assert "asked to wait" not in reply.error
    session = a.sessions[reply.session_id]
    assert session.messages == [] and session.results == {} and not session.busy.locked()


def test_a_call_cut_off_by_the_time_limit_ends_the_message_as_the_time_limit(ctx, clock):
    a, client = timed(ctx, clock, [50, 45], tool("rank_hubs", WINTER_MIDWEST), final())
    reply = a.answer(None, "Which hubs in the Midwest are most exposed?")  # the second call times out at 90 s
    assert_time_limit(a, reply)
    assert [r["timeout"] for r in client.requests] == [60, 40] and clock.now == 90


def test_no_model_call_starts_after_the_message_time_limit(ctx, clock):
    a, client = timed(ctx, clock, [50, 40], tool("list_hubs", {"region": "all"}, "toolu_1"),
                      tool("list_hubs", {"region": "all"}, "toolu_2"), final())  # fmt: skip
    reply = a.answer(None, "Which hubs are there?")  # the second call answers just as the 90 s run out
    assert_time_limit(a, reply)
    assert len(client.requests) == 2


def test_a_failure_with_less_time_left_than_the_pause_is_the_time_limit(ctx, clock):
    import anthropic

    a, client = timed(ctx, clock, [60, 29.8], tool("rank_hubs", WINTER_MIDWEST),
                      anthropic.APIConnectionError(request=_request()), final())  # fmt: skip
    reply = a.answer(None, "Which hubs are most exposed?")  # fails with 0.2 s left: no room for the 0.5 s pause
    assert_time_limit(a, reply)
    assert clock.slept == [] and len(client.requests) == 2


def test_a_bug_in_our_own_code_is_an_error_that_leaves_the_conversation_as_it_was(ctx, monkeypatch, capsys):
    import wra.agent.loop

    def broken(*args, **kwargs):
        raise KeyError("a bug")

    a, client = agent(ctx, tool("rank_hubs", WINTER_MIDWEST), final())
    monkeypatch.setattr(wra.agent.loop, "check_answer", broken)
    reply = a.answer(None, "Which hubs in the Midwest are most exposed?")
    assert reply.status == "error" and reply.error_code == "internal_error" and "KeyError" in reply.error
    session = a.sessions[reply.session_id]
    assert session.messages == [] and session.results == {} and not session.busy.locked()
    logged = capsys.readouterr().err  # the full traceback goes to the server's or the evaluation's log
    assert "Traceback" in logged and "KeyError: 'a bug'" in logged and "broken" in logged


def status_error(code, headers=None):
    import anthropic
    import httpx2

    reply = httpx2.Response(code, headers=headers or {}, request=_request())
    return anthropic.APIStatusError("failed", response=reply, body=None)


@pytest.mark.parametrize("error, wait", [
    (status_error(400), None), (status_error(401), None), (status_error(404), None),
    (status_error(408), (0.5, False)), (status_error(409), (0.5, False)), (status_error(429), (0.5, False)),
    (status_error(500), (0.5, False)), (status_error(529), (0.5, False)),
    (status_error(400, {"x-should-retry": "true"}), (0.5, False)),
    (status_error(500, {"x-should-retry": "false"}), None),
    (status_error(429, {"retry-after": "2"}), (2.0, True)),
    (status_error(429, {"retry-after-ms": "1500", "retry-after": "30"}), (1.5, True)),
    (status_error(429, {"retry-after-ms": "0", "retry-after": "30"}), (0.5, False)),  # the SDK's rule
    (status_error(429, {"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}), (0.5, False)),
    (timeout_error(), (0.5, False)), (ConnectionError("not an SDK error"), None), (KeyError("a bug"), None),
])  # fmt: skip
def test_which_failures_are_retried_and_after_what_wait(error, wait):
    from wra.agent.loop import _retry_wait

    assert _retry_wait(error) == wait


def test_a_timed_out_call_is_retried_once_within_the_time_left(ctx, clock):
    a, client = timed(ctx, clock, [60, 5, 5], timeout_error(), tool("rank_hubs", WINTER_MIDWEST), final())
    reply = a.answer(None, "Which hubs in the Midwest are most exposed?")
    assert reply.status == "answered" and clock.slept == [0.5]
    assert [r["timeout"] for r in client.requests] == [60, 29.5, 24.5]


def test_a_second_failure_of_the_same_call_ends_the_message(ctx, clock):
    a, client = timed(ctx, clock, [60, 20], timeout_error(), timeout_error(), final())
    reply = a.answer(None, "Which hubs are most exposed?")
    assert reply.error_code == "model_call_failed" and "APITimeoutError" in reply.error
    assert len(client.requests) == 2


def test_a_wait_the_api_asks_for_is_kept_when_it_fits(ctx, clock):
    a, client = timed(ctx, clock, [1, 1, 1], rate_limited("2"), tool("rank_hubs", WINTER_MIDWEST), final())
    assert a.answer(None, "Which hubs in the Midwest are most exposed?").status == "answered"
    assert clock.slept == [2.0] and len(client.requests) == 3


def test_a_wait_longer_than_the_time_left_ends_the_message_at_once(ctx, clock):
    a, client = timed(ctx, clock, [1], rate_limited("120"), final())
    reply = a.answer(None, "Which hubs are most exposed?")
    assert reply.error_code == "model_call_failed" and "120 seconds" in reply.error
    assert clock.slept == [] and len(client.requests) == 1


def test_the_prompt_asks_for_unfamiliar_terms_to_be_explained_in_plain_words(ctx):
    # Owner, milestone 4 page check: no jargon without its meaning (ASSUMPTIONS O15). Whether the model
    # follows it is read by hand in a live answer; this pins the instruction itself.
    prompt = system_prompt(ctx)
    assert "say what it means in plain words in the same sentence" in prompt
    assert "Spell out an abbreviation the first time you use it." in prompt
