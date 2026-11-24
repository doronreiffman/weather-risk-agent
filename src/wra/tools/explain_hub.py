"""explain_hub: what makes up one hub's score, where it ranks, and FEMA's cross-check figures."""

from pydantic import BaseModel, ConfigDict

from wra.scoring.config import HAZARDS, WARNING_HAZARDS
from wra.scoring.confidence import decide, gap_test
from wra.scoring.kpi import band, rank
from wra.tools.common import band_text, check_hubs, edd_what_counts, ordinal, provenance, r2
from wra.tools.context import ToolContext
from wra.tools.envelope import FEMA_FIELD_NAMES, Display, ToolResult

DESCRIPTION = (
    "Explain one hub's score: its total expected disruption days a year, band, overall rank and the hubs "
    "just above and below it, and per hazard the rate, weight, disruption days, share of the total, and its "
    "quietest and worst year. Also FEMA's own frequencies for the warning hazards, as a cross-check, and "
    "days under tropical and coastal flood warnings, which are not scored."
)


class ExplainHubArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hub_id: str


def explain_hub(ctx: ToolContext, args: ExplainHubArgs) -> ToolResult:
    check_hubs(ctx, [args.hub_id])
    cfg, scores, hub = ctx.config, ctx.scores(), args.hub_id
    score = scores[hub]
    ranked = rank(scores, "overall")
    i = next(n for n, r in enumerate(ranked) if r.hub_id == hub)
    above = ranked[i - 1] if i > 0 else None
    below = ranked[i + 1] if i + 1 < len(ranked) else None
    total = ranked[i].value

    hazards = []
    for name in HAZARDS:
        f = score.hazards[name]
        entry = {
            "hazard": name,
            "label": cfg.hazards[name].label,
            "rate": round(f.rate, 4) if name == "hurricane" else r2(f.rate),
            "weight": f.weight,
            "edd": r2(f.edd),
            "share_pct": round(100 * f.edd / score.edd) if score.edd else 0,
            "note": f.note,
        }
        if f.yearly is not None:
            quiet = min(f.yearly, key=lambda y: (f.yearly[y], y))
            worst = max(f.yearly, key=lambda y: (f.yearly[y], -y))
            entry.update(quietest_year=quiet, quietest_days=r2(f.yearly[quiet]),
                         worst_year=worst, worst_days=r2(f.yearly[worst]))  # fmt: skip
        hazards.append(entry)

    fema = ctx.data.fema[hub]
    cross_check = {
        h: {FEMA_FIELD_NAMES[field]: (round(fema[field], 4) if fema.get(field) is not None else None)
            for field in cfg.fema_cross_check[h]}
        for h in WARNING_HAZARDS
    }  # fmt: skip
    gaps = []
    if above is not None:
        gaps.append(gap_test(scores[above.hub_id], score, "overall"))
    if below is not None:
        gaps.append(gap_test(score, scores[below.hub_id], "overall"))
    confidence = decide(ctx.coverage([hub], ["overall"]), gaps, cfg.confidence, ctx.cities())

    rec = ctx.data.hubs[hub]
    data = {
        "hub_id": hub, "city": rec.city, "state": rec.state, "region": rec.region,
        "county": f"{rec.county_name} County", "station": rec.station_name,
        "total": total, "band": band(total, cfg.band_cutoffs), "rank": i + 1, "of": len(ranked),
        "above": None if above is None else {"hub_id": above.hub_id, "value": above.value},
        "below": None if below is None else {"hub_id": below.hub_id, "value": below.value},
        "hazards": hazards, "largest": max(hazards, key=lambda h: h["edd"])["hazard"],
        "fema_cross_check_events_a_year": cross_check, "supporting": ctx.supporting(hub),
    }  # fmt: skip
    return ToolResult(
        ok=True,
        tool="explain_hub",
        data=data,
        display=_display(ctx, data, score),
        provenance=provenance(ctx, ["overall"], confidence),
    )


def _display(ctx, d, score) -> Display:
    cfg = ctx.config
    columns = ["Hazard", "Rate", "Weight", "Disruption days a year", "Share of total", "Quietest year", "Worst year"]
    body = []
    for h in d["hazards"]:
        quiet = f"{h['quietest_year']} ({h['quietest_days']:.2f})" if "quietest_year" in h else ""
        worst = f"{h['worst_year']} ({h['worst_days']:.2f})" if "worst_year" in h else ""
        body.append([h["label"], h["rate"], h["weight"], h["edd"], f"{h['share_pct']}%", quiet, worst])
    body.append(["Total", None, None, d["total"], "100%", "", ""])

    place = f"{ordinal(d['rank'])} of {d['of']}"
    neighbours = []
    if d["above"]:
        neighbours.append(f"{ctx.label(d['above']['hub_id'])} {d['above']['value']:.2f} above")
    if d["below"]:
        neighbours.append(f"{ctx.label(d['below']['hub_id'])} {d['below']['value']:.2f} below")
    notes = [f"Overall rank {place}; {'; '.join(neighbours)}."]
    if score.hazards["winter"].edd > 0:
        notes.append(cfg.winter_note)
    hurricane_note = score.hazards["hurricane"].note
    if hurricane_note:
        notes.append(f"Hurricanes: {hurricane_note}")
    return Display(
        title=f"{ctx.label(d['hub_id'])}: {d['total']:.2f} expected disruption days a year, {d['band']}, {place}",
        columns=columns,
        rows=body,
        what_counts=(
            f"{edd_what_counts(ctx, cfg.weights)} Rate: days a year under warning; for hurricanes, FEMA events a "
            f"year (record {cfg.fema_period}). Years are local calendar years. {band_text(ctx)}"
        ),
        notes=notes,
    )

