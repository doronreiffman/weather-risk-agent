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
