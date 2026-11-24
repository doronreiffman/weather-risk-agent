"""The scoring rules in config/scoring.toml, read once and checked.

Everything a person might want to read or change about the score lives in that
file. This module only reads it and refuses a file that cannot be right.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

HAZARDS = ("winter", "flood", "severe_storm", "hurricane")
WARNING_HAZARDS = ("winter", "flood", "severe_storm")
BAND_LABELS = ("Low", "Moderate", "High", "Very high")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class HazardRule:
    name: str
    label: str
    weight: float
    zone_codes: tuple[str, ...] = ()
    polygon_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConfidenceRules:
    high_min_coverage: float
    low_below_coverage: float
    low_above_failed_gap_share: float
    stability_factors: tuple[float, ...]
    stability_top_n: int


@dataclass(frozen=True)
class DailyStatsRules:
    snowfall_measurable_in: float
    precipitation_measurable_in: float
    high_max_missing_share: float
    medium_max_missing_share: float


@dataclass(frozen=True)
class ScoringConfig:
    first_year: int
    last_year: int
    hazards: dict[str, HazardRule]
    fema_field: str
    fema_minimum: float
    fema_period: str
    tropical_zone_codes: tuple[str, ...]
    coastal_flood_zone_codes: tuple[str, ...]
    fema_cross_check: dict[str, tuple[str, ...]]
    band_cutoffs: tuple[float, ...]  # empty until the milestone 2 review
    confidence: ConfidenceRules
    daily: DailyStatsRules

    @property
    def weights(self) -> dict[str, float]:
        return {name: self.hazards[name].weight for name in HAZARDS}

    @property
    def years(self) -> int:
        return self.last_year - self.first_year + 1


def load_scoring_config(path: Path) -> ScoringConfig:
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    try:
        return _build(raw)
    except KeyError as error:
        raise ConfigError(f"{path}: missing setting {error}") from error


def _build(raw: dict) -> ScoringConfig:
    tables = raw["hazards"]
    if sorted(tables) != sorted(HAZARDS):
        raise ConfigError(f"hazards must be exactly {HAZARDS}, found {sorted(tables)}")
    hazards = {}
    for name in HAZARDS:
        table = tables[name]
        weight = float(table["weight"])
        if weight < 0:
            raise ConfigError(f"hazard {name}: weight must not be negative")
        hazards[name] = HazardRule(
            name=name,
            label=table["label"],
            weight=weight,
            zone_codes=tuple(table.get("zone_codes", ())),
            polygon_codes=tuple(table.get("polygon_codes", ())),
        )

    cutoffs = tuple(float(c) for c in raw["bands"]["cutoffs"])
    if cutoffs and (len(cutoffs) != len(BAND_LABELS) - 1 or list(cutoffs) != sorted(set(cutoffs)) or cutoffs[0] <= 0):
        raise ConfigError(f"band cutoffs must be empty or {len(BAND_LABELS) - 1} positive ascending numbers: {cutoffs}")

    period = raw["period"]
    if period["start_year"] > period["end_year"]:
        raise ConfigError("period start_year is after end_year")
    conf = raw["confidence"]
    daily = raw["daily_stats"]
    hurricane = tables["hurricane"]
    return ScoringConfig(
        first_year=int(period["start_year"]),
        last_year=int(period["end_year"]),
        hazards=hazards,
        fema_field=hurricane["fema_field"],
        fema_minimum=float(hurricane["fema_minimum"]),
        fema_period=hurricane["fema_period"],
        tropical_zone_codes=tuple(raw["supporting"]["tropical_zone_codes"]),
        coastal_flood_zone_codes=tuple(raw["supporting"]["coastal_flood_zone_codes"]),
        fema_cross_check={k: tuple(v) for k, v in raw["supporting"]["fema_cross_check"].items()},
        band_cutoffs=cutoffs,
        confidence=ConfidenceRules(
            high_min_coverage=float(conf["high_min_coverage"]),
            low_below_coverage=float(conf["low_below_coverage"]),
            low_above_failed_gap_share=float(conf["low_above_failed_gap_share"]),
            stability_factors=tuple(float(f) for f in conf["stability_factors"]),
            stability_top_n=int(conf["stability_top_n"]),
        ),
        daily=DailyStatsRules(
            snowfall_measurable_in=float(daily["snowfall_measurable_in"]),
            precipitation_measurable_in=float(daily["precipitation_measurable_in"]),
            high_max_missing_share=float(daily["high_max_missing_share"]),
            medium_max_missing_share=float(daily["medium_max_missing_share"]),
        ),
    )
