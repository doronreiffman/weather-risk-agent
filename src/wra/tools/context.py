"""What every tool reads: the stored data, the scoring config, today's date, and cached scores.

Built once per process. Scores under the official weights are counted once;
other weights reuse those counts (kpi.reweigh), so a what-if is cheap.
"""

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from wra import paths
from wra.scoring.confidence import warning_years_covered
from wra.scoring.config import WARNING_HAZARDS, ConfigError, ScoringConfig, load_scoring_config
from wra.scoring.kpi import HubScore, reweigh, score_hub
from wra.scoring.warning_time import days_by_year
from wra.stored import StoredData, load_stored

REGIONS = ("all", "midwest", "south", "west")


@dataclass
class ToolContext:
    data: StoredData
    config: ScoringConfig
    today: date
    _official: dict[str, HubScore] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if (self.data.period_start.year, self.data.period_end.year) != (self.config.first_year, self.config.last_year):
            raise ConfigError(
                f"the database covers {self.data.period_start} to {self.data.period_end}, but config/scoring.toml "
                f"says {self.config.first_year} to {self.config.last_year}"
            )
        self._official = {
            hub: score_hub(hub, rec.tz, self.data.warnings[hub], self.data.fema[hub], self.config, self.config.weights)
            for hub, rec in self.data.hubs.items()
        }

    # --- scores ---

    def scores(self, weights: dict[str, float] | None = None) -> dict[str, HubScore]:
        if weights is None or weights == self.config.weights:
            return self._official
        return {hub: reweigh(score, weights) for hub, score in self._official.items()}

    # --- hubs ---

    def hub_ids(self, region: str = "all") -> list[str]:
        return [h for h, rec in self.data.hubs.items() if region == "all" or rec.region == region]

    def label(self, hub_id: str) -> str:
        return f"{self.data.hubs[hub_id].city} ({hub_id})"

    def cities(self) -> dict[str, str]:
        return {h: rec.city for h, rec in self.data.hubs.items()}

    # --- coverage and supporting figures ---

    def coverage(self, hub_ids: list[str], hazards: list[str]) -> float:
        """Share of expected data present: warning years for warning hazards, a FEMA row for hurricanes."""
        cfg, present, expected = self.config, 0, 0
        needs_warnings = any(h in WARNING_HAZARDS or h == "overall" for h in hazards)
        needs_fema = any(h in ("hurricane", "overall") for h in hazards)
        for hub in hub_ids:
            if needs_warnings:
                rec = self.data.hubs[hub]
                present += warning_years_covered(self.data.warnings[hub], rec.tz, cfg.first_year, cfg.last_year)
                expected += cfg.years
            if needs_fema:
                present += cfg.fema_field in self.data.fema[hub]  # FEMA's "Not Applicable" is present, as None
                expected += 1
        return present / expected if expected else 1.0

    def supporting(self, hub_id: str) -> dict[str, float]:
        """Days a year under warnings shown beside the score, never added to it."""
        cfg, rec = self.config, self.data.hubs[hub_id]

        def per_year(codes: tuple[str, ...]) -> float:
            yearly = days_by_year(
                self.data.warnings[hub_id], list(codes), [], tz=rec.tz,
                first_year=cfg.first_year, last_year=cfg.last_year,
            )  # fmt: skip
            return round(sum(yearly.values()) / cfg.years, 2)

        return {
            "tropical_warning_days_a_year": per_year(cfg.tropical_zone_codes),
            "coastal_flood_warning_days_a_year": per_year(cfg.coastal_flood_zone_codes),
        }

    @property
    def period(self) -> str:
        return f"{self.config.first_year}-{self.config.last_year}"


def today_from_env() -> date:
    """WRA_TODAY pins "today" (the evaluation uses 2026-11-24); otherwise the machine's clock."""
    text = os.environ.get("WRA_TODAY")
    return date.fromisoformat(text) if text else date.today()


def load_context(db_path: Path | None = None, config_path: Path | None = None) -> ToolContext:
    return ToolContext(
        data=load_stored(db_path or paths.database()),
        config=load_scoring_config(config_path or paths.scoring_config()),
        today=today_from_env(),
    )
