"""Where the project's files are. One environment variable moves them all.

WRA_ROOT is the folder that holds config/ and data/. It defaults to the folder
the command is run from, which is the repository root in normal use.
"""

import os
from pathlib import Path


def root() -> Path:
    return Path(os.environ.get("WRA_ROOT") or Path.cwd())


def env_file() -> Path:
    """The file holding ANTHROPIC_API_KEY. WRA_ENV_FILE names another one, so the end-to-end script's fresh
    clone can use the original repository's .env without copying it (plan section 13, final check)."""
    return Path(os.environ.get("WRA_ENV_FILE") or root() / ".env")


def hubs_config() -> Path:
    return root() / "config" / "hubs.toml"


def scoring_config() -> Path:
    return root() / "config" / "scoring.toml"


def raw_dir() -> Path:
    return root() / "data" / "raw"


def database() -> Path:
    return root() / "data" / "wra.sqlite"


def reviewed_scores() -> Path:
    """The ranking as last reviewed, which the score-change alert compares with (docs/ALERT_DESIGN.md 5.2)."""
    return root() / "data" / "reviewed_scores.json"
