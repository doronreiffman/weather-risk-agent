"""rank_hubs: hubs ranked by expected disruption days, for one hazard or overall, official or what-if."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from wra.scoring.config import HAZARDS
from wra.scoring.confidence import decide, gap_test, stability
from wra.scoring.kpi import apply_weight_changes, band, rank
from wra.tools.common import (
    Hazard,
    HazardOrOverall,
    Region,
    band_text,
    edd_what_counts,
    hazard_label,
    provenance,
    r2,
    warning_types,
    winter_counts,
)
from wra.tools.context import ToolContext
from wra.tools.envelope import Display, ToolResult

DESCRIPTION = (
    "Rank hubs by expected disruption days a year, for one hazard or overall, for all hubs or one region. "
    "Returns each hub's figure, its band (overall only), the gap and ratio to the next hub, and whether it "
    "stands clear of the next hub given year-to-year swings. top_n limits the rows. weight_changes gives a "
    "labelled what-if ranking; leave it empty for the official ranking."
)


class WeightChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hazard: Hazard
    mode: Literal["multiply", "set"]
    value: float = Field(ge=0)


class RankHubsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hazard: HazardOrOverall
    region: Region
    top_n: int | None = Field(ge=1)
    weight_changes: list[WeightChange]


def rank_hubs(ctx: ToolContext, args: RankHubsArgs) -> ToolResult:
    cfg = ctx.config
    is_what_if = bool(args.weight_changes)
    weights = apply_weight_changes(cfg.weights, [c.model_dump() for c in args.weight_changes])
    scores = ctx.scores(weights)
    hubs = ctx.hub_ids(args.region)
    ranked = rank(scores, args.hazard, hubs)
    shown = ranked[: args.top_n] if args.top_n else ranked
    official_rank = {r.hub_id: r.rank for r in rank(ctx.scores(), args.hazard, hubs)}

    # The gaps the answer relies on (owner, 2026-11-24): those among the rows shown; for a single row,
    # "the most exposed" is a claim against the 2nd, so that gap counts too. The last row shown also
    # reports whether it stands clear of the next hub, as information that does not set the label.
    pairs = list(zip(shown, ranked[1 : len(shown) + 1]))
    counted = len(shown) - 1 if len(shown) > 1 else len(pairs)
    tests = [gap_test(scores[a.hub_id], scores[b.hub_id], args.hazard) for a, b in pairs]
    gaps = tests[:counted]
    stab = stability(scores, "overall", hubs, weights, cfg.confidence) if args.hazard == "overall" else None
    confidence = decide(ctx.coverage(hubs, [args.hazard]), gaps, cfg.confidence, ctx.cities(), stab)

    rows = []
    for i, r in enumerate(shown):
        clear = tests[i].passed if i < len(tests) else None
        row = {
            "rank": r.rank,
            "hub_id": r.hub_id,
            "city": ctx.data.hubs[r.hub_id].city,
            "value": r.value,
            "gap_to_next": r.gap_to_next,
            "ratio_to_next": r.ratio_to_next,
            "clear_of_next": clear,
        }
        if args.hazard == "overall":
            row["band"] = band(r.value, cfg.band_cutoffs)
            row["breakdown"] = {h: r2(scores[r.hub_id].hazards[h].edd) for h in HAZARDS}
        else:
            rate = scores[r.hub_id].hazards[args.hazard].rate
            row["rate"] = round(rate, 4) if args.hazard == "hurricane" else r2(rate)
        if is_what_if:
            row["official_rank"] = official_rank[r.hub_id]
        rows.append(row)

    data = {
        "hazard": args.hazard,
        "region": args.region,
        "top_n": args.top_n,
        "weights": weights,
        "is_what_if": is_what_if,
        "rows": rows,
        "gaps_tested": sum(g.passed is not None for g in gaps),
        "gaps_clear": sum(bool(g.passed) for g in gaps),
    }
    if stab is not None:
        data["stability"] = {
            "top_n": stab.top_n,
            "top": stab.base_top,
            "same_top_hub": stab.same_top_hub,
            "same_top_set": stab.same_top_set,
            "variants": [{"hazard": h, "factor": f, "top": top} for h, f, top in stab.variants],
        }
    return ToolResult(
        ok=True,
        tool="rank_hubs",
        data=data,
        display=_display(ctx, args, rows, weights, stab, scores),
        provenance=provenance(ctx, [args.hazard], confidence, is_what_if),
    )


def _display(ctx, args, rows, weights, stab, scores) -> Display:
    cfg = ctx.config
    region = "all hubs" if args.region == "all" else f"{args.region.capitalize()} hubs"
    what_if = ""
    if args.weight_changes:
        changes = ", ".join(
            f"{hazard_label(ctx, c.hazard).lower()} weight {'x' if c.mode == 'multiply' else '='} {c.value:g}"
            for c in args.weight_changes
        )
        what_if = f"WHAT-IF ({changes}), not the official ranking. "
    title = f"{what_if}{hazard_label(ctx, args.hazard)} exposure, {region}: expected disruption days a year"

    def clear(value) -> str:
        if args.hazard == "hurricane":
            return "not testable"
        return "" if value is None else ("yes" if value else "no")

    if args.hazard == "overall":
        columns = ["Rank", "Hub", "Disruption days a year", "Band", "Winter", "Flood", "Severe storms", "Hurricanes"]
        body = [
            [r["rank"], ctx.label(r["hub_id"]), r["value"], r["band"], *[r["breakdown"][h] for h in HAZARDS]]
            for r in rows
        ]
        what_counts = f"{edd_what_counts(ctx, weights)} {band_text(ctx)}"
    else:
        rate_name = "FEMA events a year" if args.hazard == "hurricane" else "Days under warning a year"
        columns = ["Rank", "Hub", rate_name, "Disruption days a year"]
        body = [[r["rank"], ctx.label(r["hub_id"]), r["rate"], r["value"]] for r in rows]
        if args.hazard == "hurricane":
            what_counts = (
                f"FEMA National Risk Index hurricane events a year for the hub's county (tropical storms included, "
                f"record {cfg.fema_period}), times {weights['hurricane']:g} disruption days per event."
            )
        else:
            what_counts = (
                f"Days a year under a {warning_types(ctx, args.hazard)} warning that covered the hub, "
                f"{cfg.first_year} to {cfg.last_year}, times weight {weights[args.hazard]:g}."
            )
    columns.append("Clear of next")
    for row, r in zip(body, rows):
        row.append(clear(r["clear_of_next"]))
    if args.weight_changes:
        columns.append("Official rank")
        for row, r in zip(body, rows):
            row.append(r["official_rank"])

    notes = []
    if winter_counts([args.hazard]):
        notes.append(cfg.winter_note)
    # Only for the official ranking: in a what-if, the variants sit around the changed weights.
    if stab is not None and not args.weight_changes and ("winter", 2.0) in [(h, f) for h, f, _ in stab.variants]:
        top = [ctx.data.hubs[h].city for h in stab.top_with("winter", 2.0)]
        notes.append(f"With winter counted double, the top {_count(len(top))} are {_join(top)}.")
    if args.hazard == "hurricane":
        notes += [f"{ctx.label(r['hub_id'])}: {scores[r['hub_id']].hazards['hurricane'].note}" for r in rows
                  if scores[r["hub_id"]].hazards["hurricane"].note]  # fmt: skip
    return Display(title=title, columns=columns, rows=body, what_counts=what_counts, notes=notes)


def _count(n: int) -> str:
    return {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}.get(n, str(n))


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
