"""The agent's settings from config/agent.toml, with WRA_MODEL and WRA_EFFORT overriding."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from wra import paths

EFFORTS = ("low", "medium", "high", "xhigh", "max")


@dataclass(frozen=True)
class AgentSettings:
    model: str
    effort: str
    max_tokens: int
    max_model_calls: int
    timeout_seconds: float
    max_retries: int
    fallback_beta: str
    fallbacks: str
    prices: dict[str, dict[str, float]]

    def cost(self, model: str, usage: dict[str, int]) -> float | None:
        """US dollars at list price; None when no price is configured for the model."""
        p = self.prices.get(model)
        if p is None:
            return None
        return (
            usage.get("input_tokens", 0) * p["input"]
            + usage.get("output_tokens", 0) * p["output"]
            + usage.get("cache_read_input_tokens", 0) * p.get("cache_read", p["input"])
            + usage.get("cache_creation_input_tokens", 0) * p["input"] * 1.25
        ) / 1_000_000


def agent_toml() -> Path:
    return paths.root() / "config" / "agent.toml"


def load_settings(path: Path | None = None) -> AgentSettings:
    with (path or agent_toml()).open("rb") as handle:
        raw = tomllib.load(handle)
    effort = os.environ.get("WRA_EFFORT") or raw["effort"]
    if effort not in EFFORTS:
        raise ValueError(f"effort {effort!r} is not one of {EFFORTS}")
    return AgentSettings(
        model=os.environ.get("WRA_MODEL") or raw["model"],
        effort=effort,
        max_tokens=int(raw["max_tokens"]),
        max_model_calls=int(raw["max_model_calls"]),
        timeout_seconds=float(raw["timeout_seconds"]),
        max_retries=int(raw["max_retries"]),
        fallback_beta=raw["fallback_beta"],
        fallbacks=raw["fallbacks"],
        prices={model: dict(p) for model, p in raw.get("prices", {}).items()},
    )
