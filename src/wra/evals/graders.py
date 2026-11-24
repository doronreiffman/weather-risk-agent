"""The five checks (docs/PLAN.md, section 10.2). All code; no model judges another model.

Each check passes, fails, or does not apply to the case (passed is None). A
case passes when every check that applies passes.

- status:   the reply's status is the expected one, and so is its what-if flag where the case sets it.
- tool:     an expected tool was called with the key arguments, somewhere in the conversation;
            and, where the case limits tools, the last turn called no other.
- hubs:     hubs_ranked agrees with the order the scoring code gives when the grader asks it directly.
- numbers:  the reply shows the table the tool returns when the grader re-runs a matching call,
            and the tool's figures equal the values pinned by hand.
- mentions: required words are present and forbidden ones absent, in the verdict and caveats.
"""

import re
from dataclasses import dataclass

from wra.agent.schemas import AgentReply
from wra.evals.cases import Case, expected_band
from wra.scoring.config import BAND_LABELS
from wra.tools.context import ToolContext
from wra.tools.registry import run_tool


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool | None  # None: does not apply to this case
    detail: str


def grade(ctx: ToolContext, case: Case, replies: list[AgentReply]) -> list[Check]:
    last = replies[-1]
    calls = [c for r in replies for c in r.trace.tool_calls]
    matching = [c for c in calls if any(e.matches(ctx, c.name, c.input) for e in case.calls)]
    return [
        _status(case, last),
        _tool(case, last, calls, matching),
        _hubs(ctx, case, last),
        _numbers(ctx, case, last, matching),
        _mentions(ctx, case, last),
    ]


def case_passed(checks: list[Check]) -> bool:
    return all(c.passed for c in checks if c.passed is not None)


def _status(case: Case, last: AgentReply) -> Check:
    problems = []
    if last.status != case.status:
        problems.append(f"status {last.status}, expected {case.status}")
    if case.is_what_if is not None and last.is_what_if != case.is_what_if:
        problems.append(f"is_what_if {last.is_what_if}, expected {case.is_what_if}")
    return Check("status", not problems, "; ".join(problems) or f"{last.status}")


def _tool(case: Case, last: AgentReply, calls, matching) -> Check:
    if not case.calls and case.allowed_tools is None:
        return Check("tool", None, "no tool expected or limited")
    problems = []
    if case.calls and not matching:
        wanted = " or ".join(f"{e.tool}{_short(e.args)}" for e in case.calls)
        made = ", ".join(f"{c.name}{_short(c.input)}" for c in calls) or "none"
        problems.append(f"expected {wanted}; calls made: {made}")
    if case.allowed_tools is not None:
        extra = sorted({c.name for c in last.trace.tool_calls} - case.allowed_tools)
        if extra:
            problems.append(f"not allowed here: {', '.join(extra)}")
    ok = f"{matching[-1].name} called with the key arguments" if matching else "only allowed tools called"
    return Check("tool", not problems, "; ".join(problems) or ok)


def _hubs(ctx: ToolContext, case: Case, last: AgentReply) -> Check:
    if case.hubs is None:
        return Check("hubs", None, "no order asserted by this case")
    expected, got = case.hubs.order(ctx), list(last.hubs_ranked)
    if case.hubs.mode == "exact":
        ok = got == expected
    elif case.hubs.mode == "prefix":
        ok = bool(got) and got == expected[: len(got)]
    else:  # "last": ends with the least exposed, in an order the ranking agrees with
        ok = bool(got) and got[-1] == expected[-1] and _in_order(got, expected)
    return Check("hubs", ok, f"asserted {got}; scoring code gives {expected} ({case.hubs.mode})")


def _numbers(ctx: ToolContext, case: Case, last: AgentReply, matching) -> Check:
    if not case.shows_table:
        return Check("numbers", None, "no table expected")
    if not matching:
        return Check("numbers", False, "no matching tool call to check the tables against")
    shown = [t.model_dump() for t in last.tables]
    problems = []
    for call in reversed(matching):  # the latest matching call is the one most likely shown
        result = run_tool(ctx, call.name, call.input)
        if not result.ok:
            problems.append(f"{call.name} failed when re-run: {result.error.message}")
            continue
        wrong_pins = {k: result.data.get(k) for k, v in case.pinned.items() if result.data.get(k) != v}
        if wrong_pins:
            problems.append(f"pinned values differ: tool gives {wrong_pins}, pinned {case.pinned}")
            continue
        if result.display.model_dump() in shown:
            pins = f"; pinned {case.pinned} hold" if case.pinned else ""
            return Check("numbers", True, f"table equals {call.name} re-run{pins}")
        problems.append(f"the reply does not show the table {call.name} returns ({result.display.title})")
    return Check("numbers", False, "; ".join(problems))


def _mentions(ctx: ToolContext, case: Case, last: AgentReply) -> Check:
    text = " ".join([last.verdict, *last.caveats])
    required = [w(ctx) if callable(w) else w for w in case.required]
    missing = [w for w in required if not _has(text, w)]
    present = [w for w in case.forbidden if w.lower() in text.lower()]
    problems = ([f"missing {missing}"] if missing else []) + ([f"forbidden {present}"] if present else [])
    if case.band_of:
        want = expected_band(ctx, case.band_of)
        named = _bands_named(text)
        required.append(want)
        if want not in named:
            problems.append(f"band {want!r} not named (bands named: {sorted(named) or 'none'})")
        elif named - {want}:
            problems.append(f"another band named as well: {sorted(named - {want})}")
    return Check("mentions", not problems, "; ".join(problems) or f"has {required or 'nothing required'}")


def _has(text: str, word: str) -> bool:
    """A whole word, or a whole number: "7.1" is not found in "17.1" or "7.15"."""
    return re.search(rf"(?<![\w.]){re.escape(word)}(?!\w|\.\d)", text, flags=re.IGNORECASE) is not None


def _bands_named(text: str) -> set[str]:
    """Band labels written as the tools write them, capitalised. "High" inside "Very high" is not High;
    "Low confidence" is the confidence label, not a band."""
    named = set()
    for label in BAND_LABELS:
        pattern = rf"(?<![\w])(?<!Very ){re.escape(label)}(?![\w])"
        if label == "Low":
            pattern += r"(?! confidence)"
        if re.search(pattern, text):
            named.add(label)
    return named


def _in_order(got: list[str], expected: list[str]) -> bool:
    positions = [expected.index(h) for h in got if h in expected]
    return len(positions) == len(got) and positions == sorted(positions)


def _short(args: dict) -> str:
    return "(" + ", ".join(f"{k}={v!r}" for k, v in args.items()) + ")"
