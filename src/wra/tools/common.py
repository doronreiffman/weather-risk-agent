"""Small pieces the tools share: argument types, labels, the provenance of a hazard's figures."""

from typing import Literal

from wra.scoring.kpi import DECIMALS
from wra.tools.context import ToolContext
from wra.tools.envelope import WARNING_NAMES, Provenance

Hazard = Literal["winter", "flood", "severe_storm", "hurricane"]
HazardOrOverall = Literal["overall", "winter", "flood", "severe_storm", "hurricane"]
Region = Literal["all", "midwest", "south", "west"]

ORDINALS = {1: "st", 2: "nd", 3: "rd"}


class UnknownHub(ValueError):
    pass


def check_hubs(ctx: ToolContext, hub_ids: list[str]) -> None:
    unknown = [h for h in hub_ids if h not in ctx.data.hubs]
    if unknown:
        known = ", ".join(f"{h} ({rec.city})" for h, rec in ctx.data.hubs.items())
        raise UnknownHub(f"No hub with id {', '.join(unknown)}. The hubs are: {known}.")


def hazard_label(ctx: ToolContext, hazard: str) -> str:
    return "Overall" if hazard == "overall" else ctx.config.hazards[hazard].label


def warning_types(ctx: ToolContext, hazard: str) -> str:
    rule = ctx.config.hazards[hazard]
    return ", ".join(WARNING_NAMES[c] for c in rule.zone_codes + rule.polygon_codes)


def r2(value: float) -> float:
    return round(value, DECIMALS)


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else ORDINALS.get(n % 10, 'th')}"


def sources_for(hazards: list[str]) -> list[str]:
    sources = []
    if any(h != "hurricane" for h in hazards):
        sources.append("iem_warning_archive")
    if any(h in ("hurricane", "overall") for h in hazards):
        sources.append("fema_nri")
    return sources


def period_for(ctx: ToolContext, hazards: list[str]) -> str:
    warnings = any(h != "hurricane" for h in hazards)
    fema = any(h in ("hurricane", "overall") for h in hazards)
    if warnings and fema:
        return f"{ctx.period}; hurricanes {ctx.config.fema_period}"
    return ctx.period if warnings else ctx.config.fema_period


def provenance(ctx: ToolContext, hazards: list[str], confidence, is_what_if: bool = False) -> Provenance:
    return Provenance(
        sources=sources_for(hazards),
        period=period_for(ctx, hazards),
        data_as_of=ctx.data.data_as_of,
        confidence=confidence.label,
        confidence_reason=confidence.reason,
        is_what_if=is_what_if,
    )


def winter_counts(hazards: list[str]) -> bool:
    return any(h in ("winter", "overall") for h in hazards)


def edd_what_counts(ctx: ToolContext, weights: dict[str, float]) -> str:
    w = weights
    return (
        f"Expected disruption days a year: days a year under a qualifying National Weather Service warning "
        f"that covered the hub, {ctx.config.first_year} to {ctx.config.last_year}, times its weight "
        f"(winter {w['winter']:g}, flood {w['flood']:g}, severe storms {w['severe_storm']:g}), plus FEMA "
        f"hurricane events a year times {w['hurricane']:g}."
    )


def band_text(ctx: ToolContext) -> str:
    c = ctx.config.band_cutoffs
    return f"Bands, for overall figures: Low below {c[0]:g}, Moderate from {c[0]:g}, High from {c[1]:g}, Very high from {c[2]:g}."

