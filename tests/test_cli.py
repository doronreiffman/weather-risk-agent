import re

import pytest

from wra import __version__
from wra.cli import main


def test_version_flag_prints_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"wra {__version__}"


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project folder holding one hub and its recorded raw responses."""
    from test_hubs import ONE_HUB
    from test_ingest_build import make_raw

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "hubs.toml").write_text(ONE_HUB)
    make_raw(tmp_path / "data" / "raw")
    monkeypatch.setenv("WRA_ROOT", str(tmp_path))
    return tmp_path


def test_ingest_builds_the_database_and_prints_rows_per_hub(project, capsys):
    assert main(["ingest"]) == 0

    out = capsys.readouterr().out
    assert "DAL  11" in out
    assert "no network used" in out
    assert (project / "data" / "wra.sqlite").exists()


def test_data_report_shows_where_the_hub_is_and_that_the_sources_agree(project, capsys):
    main(["ingest"])
    capsys.readouterr()

    assert main(["data-report"]) == 0

    out = capsys.readouterr().out
    assert "DALLAS FAA AP" in out
    assert "1 of 1 hubs agree." in out
    assert "NEEDS A LOOK" not in out
    assert "expiry_not_after_issue" in out
    assert "Winter Storm Warning" in out
    # Hurricane table: FEMA's Dallas County figure, and the one-in-N-years reading of it.
    assert re.search(r"DAL\s+Dallas\s+0\.0115\s+87 years", out)


def test_data_report_fails_when_the_sources_disagree_on_a_county(project, capsys):
    from test_ingest_build import make_raw

    def move_to_denton(payload):
        payload["features"][0]["attributes"]["STCOFIPS"] = "48121"

    make_raw(project / "data" / "raw", changes={"fema_nri": move_to_denton})
    main(["ingest"])

    assert main(["data-report"]) == 1
    assert "NEEDS A LOOK" in capsys.readouterr().out


def test_ingest_without_raw_files_fails_with_a_plain_message(tmp_path, monkeypatch, capsys):
    from test_hubs import ONE_HUB

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "hubs.toml").write_text(ONE_HUB)
    monkeypatch.setenv("WRA_ROOT", str(tmp_path))

    assert main(["ingest"]) == 1
    assert "run `wra ingest --refresh`" in capsys.readouterr().err


@pytest.fixture
def scored_project(tmp_path, monkeypatch, real_db):
    """A project folder holding the real config and the database built from the committed raw responses."""
    import shutil

    from conftest import REPO

    (tmp_path / "config").mkdir()
    for name in ("hubs.toml", "scoring.toml"):
        shutil.copy(REPO / "config" / name, tmp_path / "config" / name)
    (tmp_path / "data").mkdir()
    shutil.copy(real_db, tmp_path / "data" / "wra.sqlite")
    monkeypatch.setenv("WRA_ROOT", str(tmp_path))
    return tmp_path


def test_rank_overall_prints_the_table_bands_and_confidence(scored_project, capsys):
    assert main(["rank", "overall"]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0] == "Overall exposure, all hubs: expected disruption days a year"
    assert re.search(r"^1\s+Minneapolis \(MSP\)\s+2\.90\s+High", lines[4])
    assert "Confidence: low." in out and "FHWA-HOP-16-044" in out


def test_rank_winter_for_one_region(scored_project, capsys):
    assert main(["rank", "winter", "--region", "midwest"]) == 0
    out = capsys.readouterr().out
    hubs = re.findall(r"^\d\s+\w[\w ]*\((\w{3})\)", out, flags=re.M)
    assert hubs == ["MSP", "MCI", "ORD", "IND", "CMH"]


def test_rank_without_a_database_says_how_to_build_one(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WRA_ROOT", str(tmp_path))
    assert main(["rank", "overall"]) == 1
    assert "uv run wra ingest" in capsys.readouterr().err
