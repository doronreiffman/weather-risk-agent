import pytest

from wra import __version__
from wra.cli import main


def test_version_flag_prints_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"wra {__version__}"
