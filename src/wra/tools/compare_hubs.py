"""compare_hubs: two to four hubs side by side, each measured against the most exposed of them."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from wra.scoring.confidence import decide, gap_test
from wra.scoring.kpi import band, rank
from wra.tools.common import (
    HazardOrOverall,
    check_hubs,
    clear_text,
    edd_what_counts,
    hazard_label,
    provenance,
    r2,
    winter_counts,
)
from wra.tools.context import ToolContext
from wra.tools.envelope import Display, ToolResult

# Public zones "usually are the same as counties but in many cases are subsets of counties" (weather.gov/gis/publiczones).
FORECAST_ZONE = "forecast zone (a Weather Service warning area, usually a county or part of one)"

DESCRIPTION = (
    "Compare two to four hubs on one or more hazards (or overall). For each hazard, every hub's figure is "
    "measured against the most exposed hub of the group: the difference and the ratio are computed here, "
    "with whether the gap is larger than year-to-year swings. Includes supporting figures: days under "
    "tropical warnings and under coastal flood warnings, which are not scored."
)


class CompareHubsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hub_ids: list[str] = Field(min_length=2, max_length=4)
    hazards: list[HazardOrOverall] = Field(min_length=1)

    @field_validator("hub_ids", "hazards")
    @classmethod
    def _distinct(cls, values: list) -> list:
        if len(set(values)) != len(values):
            raise ValueError("each value may appear only once")
        return values


def compare_hubs(ctx: ToolContext, args: CompareHubsArgs) -> ToolResult:
    check_hubs(ctx, args.hub_ids)
    cfg, scores = ctx.config, ctx.scores()
    results, gaps = {}, []
    for hazard in args.hazards:
        ranked = rank(scores, hazard, args.hub_ids)
        top = ranked[0]
        rows = []
        for r in ranked:
            gap = None if r is top else gap_test(scores[top.hub_id], scores[r.hub_id], hazard)
            if gap is not None:
                gaps.append(gap)
            row = {
                "hub_id": r.hub_id,
                "city": ctx.data.hubs[r.hub_id].city,
                "value": r.value,
                "below_highest_by": r2(top.value - r.value),
                "ratio_to_highest": r2(r.value / top.value) if top.value else None,
                "clear_of_highest": None if gap is None else gap.passed,
            }
            if hazard == "overall":
                row["band"] = band(r.value, cfg.band_cutoffs)
            else:
                rate = scores[r.hub_id].hazards[hazard].rate
                row["rate"] = round(rate, 4) if hazard == "hurricane" else r2(rate)
            rows.append(row)
        results[hazard] = rows

    supporting = {h: ctx.supporting(h) for h in args.hub_ids}
    confidence = decide(ctx.coverage(args.hub_ids, list(args.hazards)), gaps, cfg.confidence, ctx.cities())
    data = {"hub_ids": args.hub_ids, "hazards": list(args.hazards), "results": results, "supporting": supporting}
    return ToolResult(
        ok=True,
        tool="compare_hubs",
        data=data,
        display=_display(ctx, args, results, supporting),
        provenance=provenance(ctx, list(args.hazards), confidence),
    )


def _display(ctx, args, results, supporting) -> Display:
    cfg, scores = ctx.config, ctx.scores()
    columns = ["Hazard", "Hub", "Rate", "Disruption days a year", "Band", "Below the highest by",
               "Ratio to the highest", "Clear of the highest"]  # fmt: skip
    body = []
    for hazard, rows in results.items():
        for r in rows:
            clear = r["clear_of_highest"]
            body.append([
                hazard_label(ctx, hazard), ctx.label(r["hub_id"]), r.get("rate"), r["value"], r.get("band"),
                r["below_highest_by"], r["ratio_to_highest"],
                "" if r is rows[0] else "not testable" if clear is None else ("yes" if clear else "no"),
            ])  # fmt: skip
    names = " and ".join(ctx.data.hubs[h].city for h in args.hub_ids)
    what_counts = (
        f"{edd_what_counts(ctx, cfg.weights)} Rate: days a year under warning; for hurricanes, FEMA events a year "
        f"(record {cfg.fema_period}); none for overall. Bands label overall figures only. "
        + clear_text("Clear of the highest", "the gap below the most exposed hub", "hurricane" in args.hazards)
    )
    notes = []
    if winter_counts(list(args.hazards)):
        notes.append(cfg.winter_note)
    if "hurricane" in args.hazards or "overall" in args.hazards:
        tropical = ", ".join(f"{ctx.data.hubs[h].city} {supporting[h]['tropical_warning_days_a_year']}" for h in args.hub_ids)
        notes.append(
            f"Not scored, shown beside FEMA's long-run figure: days a year under Hurricane, Tropical Storm or "
            f"Storm Surge Warnings for the hub's {FORECAST_ZONE}, {cfg.first_year} to {cfg.last_year}: {tropical}."
        )
        notes += [
            f"{ctx.label(h)}: {scores[h].hazards['hurricane'].note}"
            for h in args.hub_ids
            if scores[h].hazards["hurricane"].note
        ]
    if "flood" in args.hazards and any(supporting[h]["coastal_flood_warning_days_a_year"] for h in args.hub_ids):
        coastal = ", ".join(
            f"{ctx.data.hubs[h].city} {supporting[h]['coastal_flood_warning_days_a_year']}"
            for h in args.hub_ids
            if supporting[h]["coastal_flood_warning_days_a_year"]
        )
        notes.append(
            f"Not scored: days a year under Coastal Flood Warnings for the hub's whole {FORECAST_ZONE}, "
            f"{cfg.first_year} to {cfg.last_year}: {coastal}. Coastal flooding stays at the shore, while the "
            f"warning covers the zone, so these are left out of the flood figure."
        )
    if "overall" not in args.hazards:  # bands label overall figures only, so the column would be empty
        i = columns.index("Band")
        columns = columns[:i] + columns[i + 1 :]
        body = [row[:i] + row[i + 1 :] for row in body]
    return Display(title=f"{names}: expected disruption days a year, compared", columns=columns, rows=body,
                   what_counts=what_counts, notes=notes)  # fmt: skip
