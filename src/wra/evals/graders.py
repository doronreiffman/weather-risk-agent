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

import math
import re
from dataclasses import dataclass

from wra.agent.schemas import AgentReply
from wra.agent.checks import first_band
from wra.agent.grounding import numbers_in_text
from wra.evals.cases import Case, expected_band
from wra.scoring.kpi import rank
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
    if case.hubs is None and case.leads:
        return _leads(ctx, case, last)
    if case.hubs is None:
        return Check("hubs", None, "no order asserted by this case")
    expected, got = case.hubs.order(ctx), list(last.hubs_ranked)
    if not got and case.hubs.no_order_ok and _says_no_order(last.verdict):
        return Check("hubs", True, f"no order asserted, and the verdict says the hubs cannot be told apart; "
                                   f"scoring code gives {expected}")  # fmt: skip
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
    required = []
    for w in case.required:  # a callable may give one word or several
        value = w(ctx) if callable(w) else w
        required += value if isinstance(value, list) else [value]
    missing = [w for w in required if not _has(text, w)]
    present = [w for w in case.forbidden if w.lower() in text.lower()]
    problems = ([f"missing {missing}"] if missing else []) + ([f"forbidden {present}"] if present else [])
    if case.band_of:
        # The first band the verdict names is its claim; a later or caveated mention of a neighbouring
        # band ("one quieter year could drop it to Moderate") is allowed (owner, 2026-11-24).
        want = expected_band(ctx, case.band_of)
        first = first_band(last.verdict)
        required.append(want)
        if first is None:
            problems.append(f"the verdict names no band; expected {want!r}")
        elif first != want:
            problems.append(f"the first band the verdict names is {first!r}; expected {want!r}")
    return Check("mentions", not problems, "; ".join(problems) or f"has {required or 'nothing required'}")


def _has(text: str, word: str) -> bool:
    """A whole word, or a number of that value: "7.1" is not found in "17.1" or "7.15", and "1" is
    found in "1.0", since a figure may be written with trailing zeros."""
    try:
        value = float(word)
    except ValueError:
        # a final s is allowed: "earthquakes" has "earthquake" (owner, 2026-11-25)
        return re.search(rf"(?<![\w.]){re.escape(word)}s?(?!\w)", text, flags=re.IGNORECASE) is not None
    return any(math.isclose(n, value) for _, n, _ in numbers_in_text(text))


_NO_ORDER = re.compile(r"\b(neither|tied|too close|not settled|cannot be told apart|can't be told apart)\b", re.IGNORECASE)


def _says_no_order(verdict: str) -> bool:
    """The verdict states that the hubs cannot be put in order (owner, 2026-11-25: Sonnet's "neither hub is
    clearly worse" in case 6 is a right answer)."""
    return _NO_ORDER.search(verdict) is not None


def _leads(ctx: ToolContext, case: Case, last: AgentReply) -> Check:
    """For each hazard, the answer's hazard_orders must start with the hub that leads it (owner, 2026-11-25:
    a swapped comparison passes the number checks, and reading the prose for it proved fragile)."""
    claims = {o.hazard: o.hubs for o in last.hazard_orders}
    problems, pairs = [], []
    for hazard, hub_ids in case.leads:
        want = rank(ctx.scores(), hazard, list(hub_ids))[0].hub_id
        got = claims.get(hazard)
        pairs.append(f"{hazard}: {got}")
        if not got:
            problems.append(f"the answer gives no order for {hazard}")
        elif got[0] != want:
            problems.append(f"the answer puts {got[0]} first on {hazard}; the scoring code gives {want} the lead")
    return Check("hubs", not problems, "; ".join(problems) or f"each hazard's lead is right ({', '.join(pairs)})")


def _in_order(got: list[str], expected: list[str]) -> bool:
    positions = [expected.index(h) for h in got if h in expected]
    return len(positions) == len(got) and positions == sorted(positions)


def _short(args: dict) -> str:
    return "(" + ", ".join(f"{k}={v!r}" for k, v in args.items()) + ")"
