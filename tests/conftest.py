"""Shared fixtures."""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def real_db(tmp_path_factory) -> Path:
    """The database built from the committed raw responses, offline, into a temporary folder.

    Tests that pin real figures use this, never the working copy's data/wra.sqlite,
    which may be stale or missing.
    """
    from wra.hubs import load_hubs
    from wra.ingest.build import build_database

    db_path = tmp_path_factory.mktemp("real") / "wra.sqlite"
    build_database(load_hubs(REPO / "config" / "hubs.toml"), REPO / "data" / "raw", db_path)
    return db_path


@pytest.fixture(scope="session")
def real_data(real_db):
    from wra.stored import load_stored

    return load_stored(real_db)
