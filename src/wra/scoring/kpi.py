"""Expected Disruption Days per year (EDD): one hub's score, a ranking, bands, what-if weights.

Plan section 5.1:
    rate(hub, hazard)   = days under a qualifying warning, summed over the period, divided by its years
    EDD(hub, hazard)    = rate x weight
    EDD(hub, hurricane) = FEMA hurricane events per year for the hub's county x weight
    EDD(hub, overall)   = the sum of the four

Weights are passed in, never read from a global, so a what-if runs the same code
with changed weights and the official ones cannot be touched by accident.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from wra.ingest.iem import WarningEvent
from wra.scoring.config import BAND_LABELS, HAZARDS, WARNING_HAZARDS, ScoringConfig
from wra.scoring.warning_time import days_by_year

DECIMALS = 2  # figures are rounded to this before gaps and ratios, so a table adds up as shown
MODES = ("multiply", "set")


@dataclass(frozen=True)
class HazardFigure:
    hazard: str
    rate: float  # days under warning per year; for hurricanes, FEMA events per year
    weight: float
    edd: float
    yearly: dict[int, float] | None  # days under warning in each year; None for hurricanes
    note: str | None = None


@dataclass(frozen=True)
class HubScore:
    hub_id: str
    hazards: dict[str, HazardFigure]

    @property
    def edd(self) -> float:
        return sum(self.hazards[h].edd for h in HAZARDS)

    def value(self, hazard: str) -> float:
        return self.edd if hazard == "overall" else self.hazards[hazard].edd

    def yearly_edd(self, hazard: str) -> dict[int, float] | None:
        """EDD year by year. Hurricanes have no yearly series; overall adds their figure to every year."""
        if hazard == "hurricane":
            return None
        if hazard != "overall":
            figure = self.hazards[hazard]
            return {year: days * figure.weight for year, days in figure.yearly.items()}
        series = [self.yearly_edd(h) for h in WARNING_HAZARDS]
        return {year: sum(s[year] for s in series) + self.hazards["hurricane"].edd for year in series[0]}


@dataclass(frozen=True)
class RankedRow:
    rank: int
    hub_id: str
    value: float  # EDD for the hazard ranked, rounded to DECIMALS
    gap_to_next: float | None
    ratio_to_next: float | None  # None when the next hub's figure is zero


def score_hub(
    hub_id: str,
    tz: str,
    rows: Iterable[WarningEvent],
    fema: Mapping[str, float | None],
    config: ScoringConfig,
    weights: Mapping[str, float],
) -> HubScore:
    rows = list(rows)
    figures: dict[str, HazardFigure] = {}
    for name in WARNING_HAZARDS:
        rule = config.hazards[name]
        yearly = days_by_year(
            rows, list(rule.zone_codes), list(rule.polygon_codes),
            tz=tz, first_year=config.first_year, last_year=config.last_year,
        )  # fmt: skip
        rate = sum(yearly.values()) / config.years
        figures[name] = HazardFigure(name, rate, weights[name], rate * weights[name], yearly)

    frequency = fema.get(config.fema_field)
    rate, note = _hurricane_rate(frequency, config.fema_minimum)
    figures["hurricane"] = HazardFigure("hurricane", rate, weights["hurricane"], rate * weights["hurricane"], None, note)
    return HubScore(hub_id, figures)


def _hurricane_rate(frequency: float | None, minimum: float) -> tuple[float, str | None]:
    """FEMA's figure as given (open point O11). The note says what an unusual figure means."""
    if frequency is None:
        return 0.0, (
            "FEMA gives no hurricane figure for this county: it rates hurricanes Not Applicable there, "
            "outside the area where it considers a hurricane possible. Counted as zero."
        )
    if frequency == 0:
        return 0.0, "FEMA gives this county a hurricane frequency of 0."
    if abs(frequency - minimum) < 1e-9:
        return frequency, (
            f"{minimum} a year is FEMA's assumed minimum for land a hurricane could reach "
            "where no storm is on record. Used as given."
        )
    return frequency, None


def reweigh(score: HubScore, weights: Mapping[str, float]) -> HubScore:
    """The same hub under other weights. Rates and yearly days do not depend on weights, so nothing is recounted."""
    return HubScore(
        score.hub_id,
        {h: replace(f, weight=weights[h], edd=f.rate * weights[h]) for h, f in score.hazards.items()},
    )


def rank(scores: Mapping[str, HubScore], hazard: str, hub_ids: Iterable[str] | None = None) -> list[RankedRow]:
    """Highest first; ties break by hub id. Gaps and ratios use the rounded figures."""
    chosen = list(scores) if hub_ids is None else list(hub_ids)
    ordered = sorted(chosen, key=lambda hub: (-round(scores[hub].value(hazard), DECIMALS), hub))
    values = [round(scores[hub].value(hazard), DECIMALS) for hub in ordered]
    rows = []
    for i, hub in enumerate(ordered):
        nxt = values[i + 1] if i + 1 < len(values) else None
        gap = None if nxt is None else round(values[i] - nxt, DECIMALS)
        ratio = None if not nxt else round(values[i] / nxt, DECIMALS)
        rows.append(RankedRow(i + 1, hub, values[i], gap, ratio))
    return rows


def band(value: float, cutoffs: tuple[float, ...]) -> str | None:
    """The band word for a figure in days per year. None until the cut-offs are set."""
    if not cutoffs:
        return None
    return BAND_LABELS[sum(value >= c for c in cutoffs)]


def apply_weight_changes(weights: Mapping[str, float], changes: Iterable[Mapping]) -> dict[str, float]:
    """A new weights mapping with the changes applied. The input is never modified."""
    changed = dict(weights)
    for change in changes:
        hazard, mode, value = change["hazard"], change["mode"], float(change["value"])
        if hazard not in changed:
            raise ValueError(f"unknown hazard {hazard!r}; expected one of {HAZARDS}")
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
        if value < 0:
            raise ValueError(f"a weight cannot be negative: {value}")
        changed[hazard] = changed[hazard] * value if mode == "multiply" else value
    return changed
