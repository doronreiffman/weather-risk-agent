"""The evaluation runner: every case through an agent, graded, printed and saved (docs/PLAN.md, section 10.3).

The clock is pinned to EVAL_TODAY, so "last year" is always 2025. A reply with
status "error", or an exception from the agent, counts as an error, reported
apart from a wrong answer. Every conversation, tool call and check is saved
as JSON under evals/runs/<time>-<agent>/.
"""

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from wra.agent.schemas import Agent, AgentReply, Trace
from wra.evals.cases import CASES, Case
from wra.evals.graders import Check, case_passed, grade
from wra.tools.context import ToolContext

EVAL_TODAY = date(2026, 11, 24)
CHECKS = ("status", "tool", "hubs", "numbers", "mentions")


class StubAgent:
    """Answers nothing. Proves the runner and graders work end to end before any model is connected."""

    name = "stub"

    def answer(self, session_id: str | None, message: str) -> AgentReply:
        return AgentReply(
            session_id=session_id or uuid.uuid4().hex,
            status="error",
            verdict="",
            error="The stub agent has no model; it answers nothing.",
            trace=Trace(model="stub"),
        )


@dataclass
class CaseRun:
    case_id: int
    rep: int
    passed: bool
    error: bool
    seconds: float
    checks: list[Check]
    replies: list[AgentReply]


def pinned_context(ctx: ToolContext) -> ToolContext:
    """The same data and config with today pinned, for the graders."""
    return ToolContext(ctx.data, ctx.config, EVAL_TODAY)


def run_case(agent: Agent, ctx: ToolContext, case: Case, rep: int = 0) -> CaseRun:
    replies: list[AgentReply] = []
    session = None
    started = time.monotonic()
    for turn in case.turns:
        try:
            reply = agent.answer(session, turn)
        except Exception as error:  # a network or API failure is an error, not a wrong answer
            reply = AgentReply(session_id=session or "", status="error", verdict="",
                               error=f"{type(error).__name__}: {error}", trace=Trace(model=agent.name))  # fmt: skip
        replies.append(reply)
        session = reply.session_id
    checks = grade(ctx, case, replies)
    return CaseRun(
        case_id=case.id,
        rep=rep,
        passed=case_passed(checks),
        error=any(r.status == "error" for r in replies),
        seconds=round(time.monotonic() - started, 2),
        checks=checks,
        replies=replies,
    )


def run_eval(agent: Agent, ctx: ToolContext, reps: int = 1, out_root: Path | None = None, cases=CASES):
    ctx = pinned_context(ctx)
    before = os.environ.get("WRA_TODAY")
    os.environ["WRA_TODAY"] = EVAL_TODAY.isoformat()  # the agent's own tools read the same pinned date
    try:
        runs = [run_case(agent, ctx, case, rep) for case in cases for rep in range(reps)]
    finally:
        if before is None:
            os.environ.pop("WRA_TODAY", None)
        else:
            os.environ["WRA_TODAY"] = before
    out_dir = None
    if out_root is not None:
        out_dir = out_root / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{agent.name}"
        out_dir.mkdir(parents=True, exist_ok=False)
        (out_dir / "run.json").write_text(json.dumps(_record(agent, reps, runs), indent=2) + "\n")
    return runs, out_dir


def report(runs: list[CaseRun], n_cases: int, reps: int) -> str:
    mark = {True: "pass", False: "FAIL", None: "-"}
    header = ["case", "rep", *CHECKS, "result"]
    rows = [
        [str(r.case_id), str(r.rep + 1), *[mark[c.passed] for c in r.checks],
         "ERROR" if r.error else ("PASS" if r.passed else "FAIL")]
        for r in runs
    ]  # fmt: skip
    widths = [max(len(row[i]) for row in [header] + rows) for i in range(len(header))]
    lines = ["  ".join(v.ljust(w) for v, w in zip(row, widths)).rstrip() for row in [header] + rows]
    lines.insert(1, "  ".join("-" * w for w in widths))
    passed, errors = sum(r.passed for r in runs), sum(r.error for r in runs)
    replies = [reply for r in runs for reply in r.replies]
    repaired = sum(reply.trace.repaired for reply in replies)
    seconds = sum(r.seconds for r in runs) / len(runs) if runs else 0.0
    tokens_in = sum(reply.trace.usage.get("input_tokens", 0) for reply in replies)
    tokens_out = sum(reply.trace.usage.get("output_tokens", 0) for reply in replies)
    lines += [
        "",
        f"Score: {passed} of {len(runs)} case runs passed ({n_cases} cases x {reps} repetition"
        f"{'s' if reps != 1 else ''}).",
        f"Errors (no answer): {errors} of {len(runs)}. Repaired answers: {repaired} of {len(replies)}.",
        f"Time per case: {seconds:.2f} s. Tokens: {tokens_in} in, {tokens_out} out.",
    ]
    return "\n".join(lines)


def _record(agent: Agent, reps: int, runs: list[CaseRun]) -> dict:
    by_id = {c.id: c for c in CASES}
    return {
        "agent": agent.name,
        "today": EVAL_TODAY.isoformat(),
        "reps": reps,
        "runs": [
            {
                "case_id": r.case_id,
                "turns": by_id[r.case_id].turns if r.case_id in by_id else [],
                "rep": r.rep,
                "passed": r.passed,
                "error": r.error,
                "seconds": r.seconds,
                "checks": [asdict(c) for c in r.checks],
                "replies": [reply.model_dump() for reply in r.replies],
            }
            for r in runs
        ],
    }
