from collections import Counter
from pathlib import Path

import pytest

from wra.hubs import load_hubs

CONFIG = Path(__file__).parent.parent / "config" / "hubs.toml"

ONE_HUB = """
[[hub]]
id = "DAL"
city = "Dallas"
state = "TX"
region = "south"
station = "DAL"
tz = "America/Chicago"
"""


def write(tmp_path, text):
    path = tmp_path / "hubs.toml"
    path.write_text(text)
    return path


def test_the_shipped_hub_list_is_the_twelve_hubs_of_the_plan():
    hubs = load_hubs(CONFIG)

    assert [h.id for h in hubs] == [
        "ORD", "MSP", "MCI", "IND", "CMH", "MIA", "IAH", "DAL", "ATL", "MEM", "DEN", "PHX",
    ]  # fmt: skip
    assert Counter(h.region for h in hubs) == {"midwest": 5, "south": 5, "west": 2}


def test_a_repeated_hub_id_is_refused(tmp_path):
    with pytest.raises(ValueError, match="more than once"):
        load_hubs(write(tmp_path, ONE_HUB + ONE_HUB))


def test_an_unknown_region_is_refused(tmp_path):
    with pytest.raises(ValueError, match="region"):
        load_hubs(write(tmp_path, ONE_HUB.replace("south", "northeast")))


def test_an_unknown_time_zone_is_refused(tmp_path):
    with pytest.raises(ValueError, match="time zone"):
        load_hubs(write(tmp_path, ONE_HUB.replace("America/Chicago", "America/Dallas")))
