"""Where the project's files are. One environment variable moves them all.

WRA_ROOT is the folder that holds config/ and data/. It defaults to the folder
the command is run from, which is the repository root in normal use.
"""

import os
from pathlib import Path


def root() -> Path:
    return Path(os.environ.get("WRA_ROOT") or Path.cwd())


def hubs_config() -> Path:
    return root() / "config" / "hubs.toml"


def raw_dir() -> Path:
    return root() / "data" / "raw"


def database() -> Path:
    return root() / "data" / "wra.sqlite"
