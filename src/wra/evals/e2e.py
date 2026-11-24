"""Steps 4 and 5 of the final end-to-end check (plan section 13): six questions through the HTTP API only,
each reply checked against the reply schema and its expected status, and the follow-up checked for the
first question's context. Paid: scripts/e2e.sh runs it against `wra serve`.

    uv run python -m wra.evals.e2e http://127.0.0.1:8765
"""

import sys
import time
from dataclasses import dataclass

import httpx
from pydantic import ValidationError

from wra.agent.schemas import AgentReply
from wra.tools.context import ToolContext, load_context
from wra.tools.registry import run_tool

HEALTH_WAIT_SECONDS = 60
ANSWER_TIMEOUT_SECONDS = 120  # the agent gives a message 90 seconds, all model calls included


@dataclass(frozen=True)
class Question:
    text: str
    status: str
    follows: bool = False  # sent in the previous question's conversation


QUESTIONS = (
    Question("Which hubs in the Midwest are most exposed to winter disruption?", "answered"),
    Question("And which is the least exposed?", "answered", follows=True),
    Question("Compare Miami and Houston in terms of hurricane and flood exposure.", "answered"),
    Question("What percentage of days in Denver last year had snowfall?", "answered"),
    Question("Why is the Dallas hub's weather disruption risk high?", "answered"),
    Question("How exposed is our Seattle hub?", "out_of_scope"),
)


@dataclass(frozen=True)
class FollowUp:
    hub: str  # the least exposed hub of the Midwest winter ranking
    table: str  # that ranking's table title


def follow_up_expectation(ctx: ToolContext) -> FollowUp:
    """What the follow-up must show to have kept the first question's context. The hub alone is not enough:
    Columbus is last in the Midwest overall ranking too (review, 2026-11-25), so the winter table must be shown."""
    result = run_tool(ctx, "rank_hubs", {"hazard": "winter", "region": "midwest", "top_n": None, "weight_changes": []})
    return FollowUp(result.data["rows"][-1]["hub_id"], result.display.title)


def check(http: httpx.Client, expected: FollowUp) -> tuple[list[str], bool]:
    """Asks the questions in order. Returns the lines to print and whether every reply passed."""
    lines, passed, session, cost = [], 0, None, 0.0
    for q in QUESTIONS:
        response = http.post("/api/chat", json={"session_id": session if q.follows else None, "message": q.text})
        problems, reply = [], None
        if response.status_code != 200:
            problems.append(f"HTTP {response.status_code}")
        try:
            reply = AgentReply.model_validate(response.json())
        except (ValueError, ValidationError) as error:
            problems.append(f"the reply does not match the schema: {error}")
        if reply is not None:
            cost += reply.trace.usage.get("cost_usd") or 0.0
            if reply.status != q.status:
                problems.append(f"status {reply.status}, expected {q.status}")
            if q.follows and reply.session_id != session:
                problems.append("not sent in the first question's conversation")
            if q.follows and expected.hub not in reply.hubs_ranked:
                problems.append(f"does not name {expected.hub}, the least exposed hub of the first answer's ranking")
            if q.follows and expected.table not in [t.title for t in reply.tables]:
                problems.append("does not show the Midwest winter table, so the hazard may have been dropped")
            session = reply.session_id
        passed += not problems
        lines.append(f"{'FAIL' if problems else 'PASS'}  {q.text}" + (f"  ({'; '.join(problems)})" if problems else ""))
        if reply is not None:
            lines.append(f"      {reply.status}: {reply.error or reply.verdict}")
    lines.append(f"API questions: {passed} of {len(QUESTIONS)} passed. Cost at list price: ${cost:.2f}.")
    return lines, passed == len(QUESTIONS)


def wait_for_server(http: httpx.Client, seconds: float = HEALTH_WAIT_SECONDS) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if http.get("/healthz").status_code == 200:
                return True
        except httpx.TransportError:
            pass
        time.sleep(0.5)
    return False


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m wra.evals.e2e BASE_URL", file=sys.stderr)
        return 2
    with httpx.Client(base_url=argv[0], timeout=ANSWER_TIMEOUT_SECONDS) as http:
        if not wait_for_server(http):
            print(f"error: no server answered {argv[0]}/healthz within {HEALTH_WAIT_SECONDS} seconds", file=sys.stderr)
            return 1
        lines, ok = check(http, follow_up_expectation(load_context()))
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
