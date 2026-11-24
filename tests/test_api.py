"""The HTTP API through FastAPI's test client, on the scripted fake model: no network, no cost
(plan section 13, milestone 4 check)."""

import threading
from datetime import date
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from conftest import REPO
from test_agent_loop import WINTER_MIDWEST, Scripted, final, tool
from wra.agent.loop import ClaudeAgent
from wra.agent.schemas import AgentReply, ErrorCode, Trace
from wra.agent.settings import load_settings
from wra.api.app import create_app, for_page
from wra.scoring.config import load_scoring_config
from wra.stored import load_stored
from wra.tools.context import ToolContext
from wra.tools.envelope import SOURCE_NAMES, Display
from wra.tools.registry import run_tool

QUESTION = "Which hubs in the Midwest are most exposed to winter disruption?"


@pytest.fixture(scope="module")
def ctx(real_db):
    return ToolContext(load_stored(real_db), load_scoring_config(REPO / "config" / "scoring.toml"), date(2026, 11, 24))


def served(ctx, model):
    agent = ClaudeAgent(ctx, load_settings(REPO / "config" / "agent.toml"), model)
    return TestClient(create_app(agent, ctx)), agent


def ask(http, message, session_id=None):
    return http.post("/api/chat", json={"session_id": session_id, "message": message})


# --- the chat endpoint ----------------------------------------------------------------------


def test_a_question_gets_a_validated_answer_with_the_tables_and_footnote_from_code(ctx):
    http, _ = served(ctx, Scripted(tool("rank_hubs", WINTER_MIDWEST), final()))
    r = ask(http, QUESTION)
    assert r.status_code == 200
    reply = AgentReply.model_validate(r.json())
    assert reply.status == "answered" and reply.session_id and reply.evidence == ["R1"]
    result = run_tool(ctx, "rank_hubs", WINTER_MIDWEST)
    assert [t.title for t in reply.tables] == [result.display.title]
    assert reply.tables[0].rows == for_page_rows(result.display)
    assert reply.footnote.sources == [SOURCE_NAMES[s] for s in result.provenance.sources]
    assert reply.footnote.confidence == result.provenance.confidence == "low"


def for_page_rows(display):
    from wra.tools.text import cell_text

    return [[cell_text(c) for c in row] for row in display.rows]


def test_a_follow_up_with_the_same_id_uses_the_earlier_question_and_result(ctx):
    model = Scripted(tool("rank_hubs", WINTER_MIDWEST), final(),
                     final(verdict="Columbus is the least exposed.", hubs=["CMH"], hubs_from="bottom"))  # fmt: skip
    http, _ = served(ctx, model)
    first = ask(http, QUESTION).json()
    second = ask(http, "And which is the least exposed?", first["session_id"])
    assert second.status_code == 200
    body = second.json()
    assert body["status"] == "answered" and body["session_id"] == first["session_id"]
    assert body["evidence"] == ["R1"] and body["trace"]["tool_calls"] == []  # cites the first question's result
    sent = model.requests[-1]["messages"]
    assert sent[0]["content"] == QUESTION and sent[-1]["content"] == "And which is the least exposed?"


def test_an_unknown_conversation_is_404_and_reaches_no_model(ctx):
    model = Scripted(final())
    http, _ = served(ctx, model)
    r = ask(http, "And which is the least exposed?", "from-before-a-restart")
    assert r.status_code == 404
    assert r.json()["error_code"] == "unknown_conversation" and "no longer on the server" in r.json()["error"]
    assert model.requests == []


def test_a_second_message_on_a_busy_conversation_is_409(ctx):
    started, release = threading.Event(), threading.Event()

    class Slow(Scripted):
        def create(self, **request):
            started.set()
            release.wait(5)
            return super().create(**request)

    http, agent = served(ctx, Slow(tool("rank_hubs", WINTER_MIDWEST), final()))
    replies = {}
    first = threading.Thread(target=lambda: replies.update(first=ask(http, QUESTION)))
    first.start()
    assert started.wait(5)
    (session_id,) = agent.sessions
    second = ask(http, "Which hubs, again?", session_id)
    release.set()
    first.join(5)
    assert second.status_code == 409 and second.json()["error_code"] == "busy"
    assert replies["first"].status_code == 200 and replies["first"].json()["status"] == "answered"


HTTP_STATUS = {"busy": 409, "unknown_conversation": 404, "model_call_failed": 502, "time_limit": 502,
               "declined": 502, "cut_off": 502, "invalid_twice": 502, "too_many_calls": 502}  # owner, milestone 4


class Fixed:
    """An agent that always gives the same reply."""

    name = "fixed"

    def __init__(self, reply):
        self.reply = reply

    def answer(self, session_id, message):
        return self.reply


def test_every_error_code_has_an_http_status():
    assert sorted(HTTP_STATUS) == sorted(get_args(ErrorCode))


@pytest.mark.parametrize("code", sorted(HTTP_STATUS))
def test_each_failure_gets_its_http_status_and_the_reply_as_its_body(ctx, code):
    reply = AgentReply(session_id="s", status="error", verdict="", error="Plain words.", error_code=code,
                       trace=Trace(model="m"))  # fmt: skip
    r = ask(TestClient(create_app(Fixed(reply), ctx)), "Which hubs?", "s")
    assert r.status_code == HTTP_STATUS[code] and AgentReply.model_validate(r.json()) == reply


@pytest.mark.parametrize("status", ["answered", "out_of_scope", "no_data", "needs_clarification"])
def test_every_answer_that_is_not_an_error_is_200(ctx, status):
    reply = AgentReply(session_id="s", status=status, verdict="Plain words.", trace=Trace(model="m"))
    assert ask(TestClient(create_app(Fixed(reply), ctx)), "Which hubs?", "s").status_code == 200


@pytest.mark.parametrize("body", [{"session_id": None}, {"session_id": None, "message": "   "},
                                  {"session_id": None, "message": "x" * 2001},
                                  {"session_id": None, "message": "Hi", "extra": 1}])  # fmt: skip
def test_a_malformed_request_is_422_and_reaches_no_model(ctx, body):
    model = Scripted(final())
    http, _ = served(ctx, model)
    assert http.post("/api/chat", json=body).status_code == 422
    assert model.requests == []


def test_figures_go_to_the_page_as_text_by_the_command_lines_rule():
    table = Display(title="T", columns=["Hub", "EDD", "Days", "FEMA", "Gap"], rows=[["MSP", 2.9, 26, 0.0115, None]],
                    what_counts="w")  # fmt: skip
    reply = AgentReply(session_id="s", status="answered", verdict="v", tables=[table], trace=Trace(model="m"))
    assert for_page(reply)["tables"][0]["rows"] == [["MSP", "2.90", "26", "0.0115", ""]]


# --- the other endpoints and the page ---------------------------------------------------------


def test_hubs_lists_the_twelve_hubs_without_a_model_call(ctx):
    model = Scripted()
    http, _ = served(ctx, model)
    r = http.get("/api/hubs")
    assert r.status_code == 200 and [h["hub_id"] for h in r.json()["hubs"]] == list(ctx.data.hubs)
    assert model.requests == []


def test_healthz_answers_without_a_model_call(ctx):
    model = Scripted()
    http, _ = served(ctx, model)
    r = http.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok", "hubs": 12}
    assert model.requests == []


def test_the_page_is_one_file_with_no_outside_code_and_carries_femas_full_notice(ctx):
    http, _ = served(ctx, Scripted())
    r = http.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    page = r.text
    notice = next(line for line in (REPO / "README.md").read_text().splitlines() if "not endorsed by FEMA" in line)
    assert notice.count(". ") == 1 and notice in page  # both sentences, word for word as in the README
    assert "src=" not in page and "<link" not in page and "import " not in page  # no outside scripts or styles
    assert 'fetch("/api/chat"' in page
