"""The fourteen evaluation cases (docs/PLAN.md, section 10.1), written before the agent exists.

A case is one conversation. Earlier turns set it up; the checks grade the reply
to the last turn, looking at tool calls from the whole conversation, because a
follow-up may rightly reuse a result it already has.

Expected hub orders, hub names and band words are never typed here: they come
from the scoring code when the grader runs (`hubs`, callables in `required`,
`band_of`). The one figure checked by hand against the source is pinned (`pinned`).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from wra.scoring.kpi import DECIMALS, apply_weight_changes, band, rank
from wra.tools.context import ToolContext

REFERENCE_TOOLS = frozenset({"list_hubs", "get_methodology"})  # say what we cover; allowed when out of scope
FORBIDDEN_EVERYWHERE = ["$"]  # no dollar figures: costs and investment are out of scope


# --- argument matchers ------------------------------------------------------------------------


@dataclass(frozen=True)
class OneOf:
    values: tuple

    def matches(self, ctx: ToolContext, value: Any) -> bool:
        return value in self.values


@dataclass(frozen=True)
class SameSet:
    values: tuple

    def matches(self, ctx: ToolContext, value: Any) -> bool:
        return isinstance(value, list) and sorted(value) == sorted(self.values)


@dataclass(frozen=True)
class Contains:
    values: tuple

    def matches(self, ctx: ToolContext, value: Any) -> bool:
        return isinstance(value, list) and set(self.values) <= set(value)


@dataclass(frozen=True)
class Weights:
    """weight_changes that produce these weights; None means the official ones."""

    changes: tuple = ()

    def matches(self, ctx: ToolContext, value: Any) -> bool:
        try:
            produced = apply_weight_changes(ctx.config.weights, value or [])
        except (ValueError, KeyError, TypeError):
            return False
        return produced == self.weights(ctx)

    def weights(self, ctx: ToolContext) -> dict[str, float]:
        return apply_weight_changes(ctx.config.weights, [dict(c) for c in self.changes])


@dataclass(frozen=True)
class ExpectedCall:
    tool: str
    args: dict[str, Any]  # key arguments only: a plain value must be equal, a matcher must match

    def matches(self, ctx: ToolContext, name: str, given: dict) -> bool:
        if name != self.tool:
            return False
        for key, want in self.args.items():
            value = given.get(key)
            ok = want.matches(ctx, value) if hasattr(want, "matches") else value == want
            if not ok:
                return False
        return True


@dataclass(frozen=True)
class HubsCheck:
    mode: str  # "prefix": a non-empty start of the order; "exact": the whole list; "last": ends with its last hub
    order: Callable[[ToolContext], list[str]]
    no_order_ok: bool = False  # an empty order passes when the verdict says the hubs cannot be told apart


@dataclass(frozen=True)
class Case:
    id: int
    turns: list[str]
    tests: str
    status: str
    calls: list[ExpectedCall] = field(default_factory=list)  # any one, somewhere in the conversation
    allowed_tools: frozenset[str] | None = None  # None: any tool; otherwise only these, in the last turn
    hubs: HubsCheck | None = None
    is_what_if: bool | None = None
    required: list[str | Callable[[ToolContext], str]] = field(default_factory=list)  # whole words or numbers
    band_of: str | None = None  # the first band the verdict names must be this hub's real band (owner, 2026-11-24)
    leads: tuple[tuple[str, tuple[str, ...]], ...] = ()  # (hazard, hubs): hazard_orders must name its leader first
    forbidden: list[str] = field(default_factory=lambda: list(FORBIDDEN_EVERYWHERE))
    pinned: dict[str, Any] = field(default_factory=dict)  # figures in the matching tool result's data
    shows_table: bool = True  # whether the expected tool's table must be among the reply's tables


# --- expected orders, from the scoring code ---------------------------------------------------


def _order(hazard: str, region: str = "all", top: int | None = None, weights: Weights | None = None):
    def order(ctx: ToolContext) -> list[str]:
        scores = ctx.scores(weights.weights(ctx) if weights else None)
        ids = [r.hub_id for r in rank(scores, hazard, ctx.hub_ids(region))]
        return ids[:top] if top else ids

    return order


def _pair_order(hub_ids: tuple[str, ...], hazard: str):
    return lambda ctx: [r.hub_id for r in rank(ctx.scores(), hazard, list(hub_ids))]


def expected_band(ctx: ToolContext, hub_id: str) -> str:
    """Banded on the figure as the tools show it, rounded."""
    return band(round(ctx.scores()[hub_id].edd, DECIMALS), ctx.config.band_cutoffs)


def _weights_as_figures(ctx: ToolContext) -> list[str]:
    """Each distinct weight, as a whole figure: today 1 (the three warning hazards) and 5 (hurricanes)."""
    return list(dict.fromkeys(f"{w:g}" for w in ctx.config.weights.values()))


def _city(order, index: int):
    return lambda ctx: ctx.data.hubs[order(ctx)[index]].city


OFFICIAL = Weights()
HURRICANE_DOUBLE = Weights(((("hazard", "hurricane"), ("mode", "multiply"), ("value", 2.0)),))

Q1 = "Which hubs in the Midwest are most exposed to winter disruption?"
Q2 = "Compare Miami and Houston in terms of hurricane and flood exposure."
OVERALL = "Which hubs are most exposed overall?"
WHAT_IF = "What if a hurricane counted double?"

WINTER_MIDWEST = ExpectedCall("rank_hubs", {"hazard": "winter", "region": "midwest", "weight_changes": OFFICIAL})
MIA_IAH = ("MIA", "IAH")

CASES = [
    Case(1, [Q1], "Assignment question. Ranking by one hazard and region.", "answered",
         calls=[WINTER_MIDWEST], hubs=HubsCheck("prefix", _order("winter", "midwest")),
         required=[_city(_order("winter", "midwest"), 0)]),
    Case(2, [Q2], "Assignment question. Comparison across two hazards.", "answered",
         calls=[ExpectedCall("compare_hubs", {"hub_ids": SameSet(MIA_IAH), "hazards": Contains(("hurricane", "flood"))})],
         required=["Miami", "Houston"], leads=(("hurricane", MIA_IAH), ("flood", MIA_IAH))),
    Case(3, ["What percentage of days in Denver last year had snowfall?"],
         "Assignment question. 'Last year' resolved in code.", "answered",
         calls=[ExpectedCall("daily_weather_stats", {
             "hub_id": "DEN", "metric": "snowfall", "threshold": "measurable",
             "start_year": OneOf((None, 2025)), "end_year": OneOf((None, 2025))})],
         required=["7.1"], pinned={"period": "2025", "days_meeting": 26, "days_observed": 364}),
    Case(4, ["Why is the Dallas hub's weather disruption risk high?"],
         "Assignment question. Explains drivers and states the real band.", "answered",
         calls=[ExpectedCall("explain_hub", {"hub_id": "DAL"})], required=["Dallas"], band_of="DAL"),
    Case(5, [Q1, "And which is the least exposed?"], "Follow-up that keeps region and hazard.", "answered",
         calls=[WINTER_MIDWEST], hubs=HubsCheck("last", _order("winter", "midwest")),
         required=[_city(_order("winter", "midwest"), -1)]),
    Case(6, [Q2, "Which of the two is worse overall?"], "Follow-up that changes the hazard.", "answered",
         calls=[ExpectedCall("compare_hubs", {"hub_ids": SameSet(MIA_IAH), "hazards": Contains(("overall",))}),
                ExpectedCall("rank_hubs", {"hazard": "overall", "weight_changes": OFFICIAL})],
         hubs=HubsCheck("exact", _pair_order(MIA_IAH, "overall"), no_order_ok=True),
         required=[_city(_pair_order(MIA_IAH, "overall"), 0)]),
    Case(7, [OVERALL, WHAT_IF], "What-if, flagged as such.", "answered",
         calls=[ExpectedCall("rank_hubs", {"hazard": "overall", "region": "all", "weight_changes": HURRICANE_DOUBLE})],
         hubs=HubsCheck("prefix", _order("overall", weights=HURRICANE_DOUBLE)), is_what_if=True),
    Case(8, [OVERALL, WHAT_IF, "Go back to the normal ranking."], "The official weights were not changed.",
         "answered", calls=[ExpectedCall("rank_hubs", {"hazard": "overall", "region": "all", "weight_changes": OFFICIAL})],
         hubs=HubsCheck("prefix", _order("overall")), is_what_if=False),
    Case(9, ["Which three hubs are most exposed overall?"], "Overall ranking.", "answered",
         calls=[ExpectedCall("rank_hubs", {"hazard": "overall", "region": "all", "weight_changes": OFFICIAL})],
         hubs=HubsCheck("exact", _order("overall", top=3))),
    Case(10, ["How is the score calculated, and what are the weights?"], "Methodology comes from the tool.",
         "answered", calls=[ExpectedCall("get_methodology", {})], required=[_weights_as_figures]),
    Case(11, ["How exposed is our Seattle hub?"], "Out of scope: no such hub.", "out_of_scope",
         allowed_tools=REFERENCE_TOOLS, required=["Seattle"], shows_table=False),
    Case(12, ["Will it snow in Chicago next week?"], "Out of scope: forecast.", "out_of_scope",
         allowed_tools=REFERENCE_TOOLS, shows_table=False),
    Case(13, ["Which hub is most at risk from earthquakes?"], "Out of scope: hazard not covered.", "out_of_scope",
         allowed_tools=REFERENCE_TOOLS, required=["earthquake"], shows_table=False),
    Case(14, ["What percentage of days in Denver had snowfall in 2010?"],
         "Data does not cover the year. Says so, gives the covered range.", "no_data",
         calls=[ExpectedCall("daily_weather_stats", {"hub_id": "DEN", "metric": "snowfall",
                                                     "start_year": 2010, "end_year": 2010})],
         required=["2016", "2025"], shows_table=False),
]  # fmt: skip
