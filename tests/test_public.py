"""Public mode's door: HTTP Basic sign-in in front of every route but /healthz (docs/DEPLOY_DESIGN.md 5.1 and
5.2). On the scripted fake model: no network, no cost."""

import base64
from datetime import date

import pytest
from fastapi.testclient import TestClient

from conftest import REPO
from test_agent_loop import WINTER_MIDWEST, Scripted, final, tool
from wra.agent.loop import ClaudeAgent
from wra.agent.settings import load_settings
from wra.api.app import create_app
from wra.api.public import access_code_from_env, is_public
from wra.scoring.config import load_scoring_config
from wra.stored import load_stored
from wra.tools.context import ToolContext

CODE = "pa:ss-ü"  # a colon and a non-ASCII letter: the pair splits at the first colon, compared as UTF-8 bytes
QUESTION = "Which hubs in the Midwest are most exposed to winter disruption?"
GUARDED = ["/", "/api/hubs", "/docs", "/openapi.json"]


@pytest.fixture(scope="module")
def ctx(real_db):
    return ToolContext(load_stored(real_db), load_scoring_config(REPO / "config" / "scoring.toml"), date(2026, 11, 24))


def served(ctx, *responses, access_code=CODE):
    model = Scripted(*responses)
    agent = ClaudeAgent(ctx, load_settings(REPO / "config" / "agent.toml"), model)
    return TestClient(create_app(agent, ctx, access_code=access_code)), model


def basic(raw: bytes) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


def test_the_door_refuses_without_or_with_wrong_credentials(ctx):
    http, model = served(ctx, final())
    for auth in (None, ("analyst", "wrong"), ("admin", CODE)):
        for path in GUARDED:
            r = http.get(path, auth=auth)
            assert r.status_code == 401, (path, auth)
            assert r.headers["www-authenticate"].startswith("Basic")
        r = http.post("/api/chat", json={"session_id": None, "message": QUESTION}, auth=auth)
        assert r.status_code == 401
    assert model.requests == []


def test_the_door_lets_the_right_credentials_through(ctx):
    http, _ = served(ctx, tool("rank_hubs", WINTER_MIDWEST), final())
    auth = ("analyst", CODE)
    assert http.get("/", auth=auth).status_code == 200
    assert len(http.get("/api/hubs", auth=auth).json()["hubs"]) == 12
    r = http.post("/api/chat", json={"session_id": None, "message": QUESTION}, auth=auth)
    assert r.status_code == 200 and r.json()["status"] == "answered"


def test_healthz_needs_no_sign_in(ctx):
    http, _ = served(ctx)
    r = http.get("/healthz")
    assert r.status_code == 200 and r.json() == {"status": "ok", "hubs": 12}


@pytest.mark.parametrize("headers", [
    {"Authorization": "Bearer x"},
    {"Authorization": "Basic !!!"},
    basic(b"nocolon"),
    basic(b"\xff\xfe"),  # not UTF-8
], ids=["not-basic", "not-base64", "no-colon", "not-utf8"])  # fmt: skip
def test_malformed_sign_in_headers_get_401(ctx, headers):
    http, _ = served(ctx)
    assert http.get("/", headers=headers).status_code == 401


@pytest.mark.parametrize("host", ["x/healthz?", "x/healthz#", "x/healthz"])
def test_a_forged_host_header_does_not_open_the_door(ctx, host):
    # the door must decide on the path the router serves, not on a URL rebuilt from the Host header, where a
    # host of "x/healthz?" turns "/api/hubs" into a query string after "/healthz" (whole-branch review)
    http, model = served(ctx, final())
    assert http.get("/api/hubs", headers={"Host": host}).status_code == 401
    r = http.post("/api/chat", json={"session_id": None, "message": QUESTION}, headers={"Host": host})
    assert r.status_code == 401 and model.requests == []


def test_no_door_without_an_access_code(ctx):
    http, _ = served(ctx, access_code=None)
    assert http.get("/").status_code == 200


def test_which_addresses_are_public():
    assert [is_public(h) for h in ("127.0.0.1", "localhost", "::1")] == [False, False, False]
    assert [is_public(h) for h in ("0.0.0.0", "192.168.1.5")] == [True, True]


@pytest.mark.parametrize(("value", "expected"), [(None, None), ("", None), ("   ", None), (" abc ", "abc")])
def test_a_blank_access_code_counts_as_missing(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("WRA_ACCESS_CODE", raising=False)
    else:
        monkeypatch.setenv("WRA_ACCESS_CODE", value)
    assert access_code_from_env() == expected
