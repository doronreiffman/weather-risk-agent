"""get_methodology: how the score works, read from the same config the scoring code uses."""

from pydantic import BaseModel, ConfigDict

from wra.scoring.config import BAND_LABELS, HAZARDS, WARNING_HAZARDS
from wra.tools.common import band_text, edd_what_counts, warning_types
from wra.tools.context import ToolContext
from wra.tools.envelope import SOURCE_NAMES, Display, Provenance, ToolResult

DESCRIPTION = (
    "How the score is calculated: the hazards, which warnings count for each, the weights, the bands, the "
    "period, the sources and the known limits. Use for questions about the method or the weights."
)


class MethodologyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def get_methodology(ctx: ToolContext, args: MethodologyArgs) -> ToolResult:
    cfg = ctx.config
    counted = {h: f"Time under {warning_types(ctx, h)} warnings that covered the hub" for h in WARNING_HAZARDS}
    counted["hurricane"] = "FEMA hurricane events a year for the hub's county, tropical storms included"
    unit = {h: "disruption days per day under warning" for h in WARNING_HAZARDS}
    unit["hurricane"] = "disruption days per event"
    hazards = [
        {
            "hazard": h,
            "label": cfg.hazards[h].label,
            "counted": counted[h],
            "weight": cfg.hazards[h].weight,
            "weight_unit": unit[h],
            "source": "fema_nri" if h == "hurricane" else "iem_warning_archive",
            "period": cfg.fema_period if h == "hurricane" else ctx.period,
        }
        for h in HAZARDS
    ]
    c = cfg.band_cutoffs
    data = {
        "score": "Expected disruption days a year (EDD), summed over four hazards.",
        "hazards": hazards,
        "weights": cfg.weights,
        "bands": {"labels": list(BAND_LABELS), "cutoffs": list(c), "applies_to": cfg.bands_apply_to},
        "period": ctx.period,
        "sources": {k: v for k, v in SOURCE_NAMES.items()},
        "fema_release": ctx.data.fema_release,
        "known_limits": list(cfg.known_limits),
        "winter_note": cfg.winter_note,
        "not_scored": "Watches, advisories, river and area flood warnings, coastal flood warnings, cold and "
        "wind-chill warnings, high-wind warnings, heat, wildfire, earthquakes.",
    }
    return ToolResult(
        ok=True,
        tool="get_methodology",
        data=data,
        display=Display(
            title="How the exposure score is calculated",
            columns=["Hazard", "What is counted", "Weight", "Source", "Period"],
            rows=[[h["label"], h["counted"], f"{h['weight']:g} {h['weight_unit']}", SOURCE_NAMES[h["source"]],
                   h["period"]] for h in hazards],  # fmt: skip
            what_counts=f"{edd_what_counts(ctx, cfg.weights)} {band_text(ctx)} Not counted: {data['not_scored']}",
            notes=[cfg.winter_note, *cfg.known_limits],
        ),
        provenance=Provenance(
            sources=list(SOURCE_NAMES), period=f"{ctx.period}; hurricanes {cfg.fema_period}",
            data_as_of=ctx.data.data_as_of, confidence="high",
            confidence_reason="The method is fixed in config/scoring.toml; it is a rule, not a measurement.",
        ),  # fmt: skip
    )
