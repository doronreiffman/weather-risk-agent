"""Confidence, computed in code: a label and a one-line reason (plan section 5.6).

Three tests:
- coverage:   the share of expected data that is present;
- separation: is the gap between two hubs larger than the combined standard
              error of their yearly figures? Hurricanes have no yearly series,
              so their gaps cannot be tested, and a result resting on one is at
              most medium (owner, 2026-11-24);
- stability:  overall rankings only. Each weight halved and doubled: does the
              top hub stay on top, and is the top three the same set?

Callers choose which gaps to test (docs/ASSUMPTIONS.md, milestone 2 point 10):
the gaps among the rows a ranking shows, between the hubs a comparison names,
or around one hub's place in the overall ranking.
"""

import math
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from wra.ingest.iem import WarningEvent
from wra.scoring.config import HAZARDS, ConfidenceRules, DailyStatsRules
from wra.scoring.kpi import HubScore, rank, reweigh

_FACTOR_WORDS = {0.5: "halved", 2.0: "doubled"}
_HAZARD_WORDS = {"winter": "winter", "flood": "flood", "severe_storm": "severe storm", "hurricane": "hurricane"}


@dataclass(frozen=True)
class Confidence:
    label: str  # high, medium, low
    reason: str


@dataclass(frozen=True)
class Gap:
    upper: str
    lower: str
    gap: float
    noise: float | None  # combined standard error; None when the gap cannot be tested

    @property
    def passed(self) -> bool | None:
        return None if self.noise is None else self.gap > self.noise


@dataclass(frozen=True)
class Stability:
    top_n: int
    base_top: list[str]
    variants: list[tuple[str, float, list[str]]]  # (hazard, factor, top hub ids)

    @property
    def same_top_hub(self) -> bool:
        return all(top[0] == self.base_top[0] for _, _, top in self.variants)

    @property
    def same_top_set(self) -> bool:
        return all(set(top) == set(self.base_top) for _, _, top in self.variants)

    def top_with(self, hazard: str, factor: float) -> list[str]:
        return next(top for h, f, top in self.variants if (h, f) == (hazard, factor))


def standard_error(yearly: Mapping[int, float] | None) -> float | None:
    if yearly is None or len(yearly) < 2:
        return None
    return statistics.stdev(yearly.values()) / math.sqrt(len(yearly))


def gap_test(upper: HubScore, lower: HubScore, hazard: str) -> Gap:
    """Is `upper` really above `lower` on this hazard? Values unrounded."""
    a, b = standard_error(upper.yearly_edd(hazard)), standard_error(lower.yearly_edd(hazard))
    noise = None if a is None or b is None else math.hypot(a, b)
    return Gap(upper.hub_id, lower.hub_id, upper.value(hazard) - lower.value(hazard), noise)


def stability(
    scores: Mapping[str, HubScore],
    hazard: str,
    hub_ids: Iterable[str],
    weights: Mapping[str, float],
    rules: ConfidenceRules,
) -> Stability:
    """Re-rank with each weight halved and doubled, around the weights in use."""
    hub_ids = list(hub_ids)
    top_n = min(rules.stability_top_n, len(hub_ids))

    def top(w: Mapping[str, float]) -> list[str]:
        changed = {h: reweigh(scores[h], w) for h in hub_ids}
        return [r.hub_id for r in rank(changed, hazard, hub_ids)[:top_n]]

    variants = [
        (name, factor, top({**weights, name: weights[name] * factor}))
        for name in HAZARDS
        for factor in rules.stability_factors
    ]
    return Stability(top_n, top(weights), variants)


def decide(
    coverage: float,
    gaps: list[Gap],
    rules: ConfidenceRules,
    names: Mapping[str, str],
    stab: Stability | None = None,
) -> Confidence:
    tested = [g for g in gaps if g.passed is not None]
    failed = [g for g in tested if not g.passed]
    untestable = [g for g in gaps if g.passed is None]
    top_moves = stab is not None and not stab.same_top_hub
    set_moves = stab is not None and not stab.same_top_set

    low = (
        coverage < rules.low_below_coverage
        or (tested and len(failed) / len(tested) > rules.low_above_failed_gap_share)
        or top_moves
    )
    high = coverage >= rules.high_min_coverage and not failed and not untestable and not set_moves
    label = "low" if low else "high" if high else "medium"

    parts = [f"Data coverage {coverage:.0%} (the share of the records these figures need that the data holds)."]
    if tested and not failed:
        parts.append("Every gap tested is larger than the hubs' year-to-year swings.")
    elif failed:
        holding = [g for g in tested if g.passed]
        text = f"{len(failed)} of {len(tested)} gaps are within the hubs' year-to-year swings"
        if holding and len(holding) <= 3:
            text += "; clear: " + ", ".join(f"{names[g.upper]} above {names[g.lower]}" for g in holding)
        parts.append(text + ".")
    if untestable:
        parts.append(
            "Hurricane figures are one long-run FEMA figure with no yearly values, so their gaps cannot be tested."
        )
    if stab is not None:
        if not set_moves and not top_moves:
            parts.append(f"The top hub and top {stab.top_n} are unchanged with any weight halved or doubled.")
        else:
            moved = [
                f"{_HAZARD_WORDS[h]} {_FACTOR_WORDS.get(f, f'x{f:g}')}"
                for h, f, top in stab.variants
                if (top[0] != stab.base_top[0] if top_moves else set(top) != set(stab.base_top))
            ]
            what = "top hub" if top_moves else f"top {stab.top_n}"
            parts.append(f"The {what} changes with {', '.join(moved)}.")
    return Confidence(label, " ".join(parts))


def warning_years_covered(rows: Iterable[WarningEvent], tz: str, first_year: int, last_year: int) -> int:
    """Years of the period in which the archive holds any row for the hub, of any type or level."""
    zone = ZoneInfo(tz)
    bounds = [
        (year, datetime(year, 1, 1, tzinfo=zone).astimezone(UTC), datetime(year + 1, 1, 1, tzinfo=zone).astimezone(UTC))
        for year in range(first_year, last_year + 1)
    ]
    covered = set()
    for r in rows:
        for year, start, end in bounds:
            if r.issue_utc < end and r.expire_utc > start:
                covered.add(year)
    return len(covered)


def daily_confidence(missing: int, total: int, rules: DailyStatsRules) -> Confidence:
    share = missing / total if total else 1.0
    label = (
        "high"
        if share <= rules.high_max_missing_share
        else "medium"
        if share <= rules.medium_max_missing_share
        else "low"
    )
    return Confidence(label, f"{missing} of {total} days missing ({share:.1%}).")
