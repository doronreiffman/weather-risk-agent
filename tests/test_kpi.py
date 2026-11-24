"""Rates, Expected Disruption Days, ranking, bands and what-if weights, on hand-built inputs."""

import dataclasses
from datetime import UTC, datetime
from pathlib import Path

import pytest

from wra.ingest.iem import WarningEvent
from wra.scoring.config import ConfigError, load_scoring_config
from wra.scoring.kpi import apply_weight_changes, band, rank, score_hub

CONFIG_FILE = Path(__file__).resolve().parents[1] / "config" / "scoring.toml"
CONFIG = load_scoring_config(CONFIG_FILE)


def zone_warning(issue: str, hours: float, phenomena: str = "WS", event_id: int = 1) -> WarningEvent:
    start = datetime.fromisoformat(issue).replace(tzinfo=UTC)
    return WarningEvent(
        matched_by="zone", wfo="MPX", vtec_year=start.year, phenomena=phenomena, significance="W",
        event_id=event_id, ugc="MNZ060", issue_utc=start,
        expire_utc=datetime.fromtimestamp(start.timestamp() + hours * 3600, UTC), name="test",
    )  # fmt: skip


def polygon_warning(issue: str, hours: float, phenomena: str, event_id: int) -> WarningEvent:
    w = zone_warning(issue, hours, phenomena, event_id)
    return dataclasses.replace(w, matched_by="polygon", ugc=None)


# --- the config ----------------------------------------------------------------------------


def test_the_config_holds_the_agreed_weights_and_period():
    assert CONFIG.weights == {"winter": 1.0, "flood": 1.0, "severe_storm": 1.0, "hurricane": 5.0}
    assert (CONFIG.first_year, CONFIG.last_year) == (2016, 2025)
    assert CONFIG.hazards["winter"].zone_codes == ("WS", "BZ", "IS", "LE")
    assert CONFIG.hazards["severe_storm"].polygon_codes == ("TO", "SV")
    # Flood is flash flood warnings only: coastal flood left the score at the review (O10).
    assert (CONFIG.hazards["flood"].zone_codes, CONFIG.hazards["flood"].polygon_codes) == ((), ("FF",))
    assert CONFIG.coastal_flood_zone_codes == ("CF",)


def test_a_config_with_cutoffs_out_of_order_is_refused(tmp_path):
    text = CONFIG_FILE.read_text()
    bad = tmp_path / "scoring.toml"
    bad.write_text(text.replace("cutoffs = []", "cutoffs = [5, 2, 10]"))
    with pytest.raises(ConfigError, match="ascending"):
        load_scoring_config(bad)


def test_a_config_missing_a_hazard_is_refused(tmp_path):
    text = CONFIG_FILE.read_text()
    bad = tmp_path / "scoring.toml"
    bad.write_text(text.replace("[hazards.flood]", "[hazards.flooding]"))
    with pytest.raises(ConfigError, match="flood"):
        load_scoring_config(bad)


# --- one hub's score -----------------------------------------------------------------------


def test_a_hubs_score_is_days_under_warning_per_year_times_weight_plus_hurricanes():
    rows = [
        zone_warning("2017-01-10T00:00", 36),  # 1.5 days of winter warning in 2017
        zone_warning("2019-12-01T00:00", 24, phenomena="BZ", event_id=2),  # 1 day in 2019
        polygon_warning("2018-06-01T00:00", 3, "FF", 3),  # 0.125 day of flood warning
        polygon_warning("2018-06-02T00:00", 1.2, "SV", 4),  # 0.05 day of severe storm warning
    ]
    score = score_hub("MSP", "America/Chicago", rows, {"HRCN_AFREQ": 0.2}, CONFIG, CONFIG.weights)

    winter = score.hazards["winter"]
    assert winter.rate == pytest.approx(2.5 / 10)
    assert winter.edd == pytest.approx(0.25)
    assert winter.yearly[2017] == pytest.approx(1.5) and winter.yearly[2016] == 0.0
    assert score.hazards["flood"].rate == pytest.approx(0.0125)
    assert score.hazards["severe_storm"].rate == pytest.approx(0.005)
    hurricane = score.hazards["hurricane"]
    assert (hurricane.rate, hurricane.weight, hurricane.edd) == (0.2, 5.0, pytest.approx(1.0))
    assert hurricane.yearly is None
    assert score.edd == pytest.approx(0.25 + 0.0125 + 0.005 + 1.0)


def test_the_overall_yearly_series_adds_the_hurricane_figure_to_every_year():
    rows = [zone_warning("2017-01-10T00:00", 48)]
    score = score_hub("MSP", "America/Chicago", rows, {"HRCN_AFREQ": 0.1}, CONFIG, CONFIG.weights)
    yearly = score.yearly_edd("overall")
    assert yearly[2017] == pytest.approx(2.0 + 0.5)
    assert yearly[2016] == pytest.approx(0.5)
    assert score.yearly_edd("hurricane") is None


def test_no_fema_hurricane_figure_counts_as_zero_and_says_why():
    score = score_hub("DEN", "America/Denver", [], {"HRCN_AFREQ": None}, CONFIG, CONFIG.weights)
    hurricane = score.hazards["hurricane"]
    assert hurricane.edd == 0.0
    assert "no hurricane figure" in hurricane.note and "Not Applicable" in hurricane.note


def test_femas_assumed_minimum_is_used_as_given_and_named():
    score = score_hub("ORD", "America/Chicago", [], {"HRCN_AFREQ": 0.010000000000000038}, CONFIG, CONFIG.weights)
    hurricane = score.hazards["hurricane"]
    assert hurricane.edd == pytest.approx(0.05)
    assert "assumed minimum" in hurricane.note


def test_a_fema_zero_is_used_as_given():
    score = score_hub("MCI", "America/Chicago", [], {"HRCN_AFREQ": 0.0}, CONFIG, CONFIG.weights)
    assert score.hazards["hurricane"].edd == 0.0
    assert "0" in score.hazards["hurricane"].note


# --- ranking -------------------------------------------------------------------------------


def _scores(values: dict[str, float]):
    """Hubs whose only exposure is a hurricane figure, so the score is easy to set."""
    return {
        hub: score_hub(hub, "America/Chicago", [], {"HRCN_AFREQ": v / 5.0}, CONFIG, CONFIG.weights)
        for hub, v in values.items()
    }


def test_hubs_rank_highest_first_with_ties_broken_by_hub_id():
    ranked = rank(_scores({"DAL": 1.0, "ATL": 3.0, "MEM": 1.0, "IAH": 2.0}), "hurricane")
    assert [(r.rank, r.hub_id) for r in ranked] == [(1, "ATL"), (2, "IAH"), (3, "DAL"), (4, "MEM")]


def test_gap_and_ratio_to_the_next_hub_use_the_figures_as_shown():
    ranked = rank(_scores({"ATL": 3.004, "IAH": 1.5, "DAL": 0.0}), "overall")
    assert [r.value for r in ranked] == [3.0, 1.5, 0.0]
    assert ranked[0].gap_to_next == 1.5 and ranked[0].ratio_to_next == 2.0
    assert ranked[1].gap_to_next == 1.5 and ranked[1].ratio_to_next is None  # next hub is zero
    assert ranked[2].gap_to_next is None and ranked[2].ratio_to_next is None


def test_rank_can_be_limited_to_some_hubs():
    ranked = rank(_scores({"ATL": 3.0, "IAH": 2.0, "DAL": 1.0}), "overall", hub_ids=["DAL", "IAH"])
    assert [r.hub_id for r in ranked] == ["IAH", "DAL"]
    assert ranked[0].rank == 1


# --- bands ---------------------------------------------------------------------------------


def test_bands_follow_the_cutoffs_and_include_the_lower_edge():
    cutoffs = (2.0, 5.0, 10.0)
    assert [band(v, cutoffs) for v in (0.0, 1.99, 2.0, 4.99, 5.0, 10.0, 25.0)] == [
        "Low", "Low", "Moderate", "Moderate", "High", "Very high", "Very high",
    ]  # fmt: skip


def test_no_band_until_the_cutoffs_are_set():
    assert band(7.0, ()) is None


# --- what-if weights -----------------------------------------------------------------------


def test_weight_changes_multiply_or_set_and_leave_the_official_weights_alone():
    official = dict(CONFIG.weights)
    changed = apply_weight_changes(
        CONFIG.weights,
        [{"hazard": "hurricane", "mode": "multiply", "value": 2}, {"hazard": "flood", "mode": "set", "value": 0.5}],
    )
    assert changed == {"winter": 1.0, "flood": 0.5, "severe_storm": 1.0, "hurricane": 10.0}
    assert CONFIG.weights == official


@pytest.mark.parametrize(
    "change, message",
    [
        ({"hazard": "heat", "mode": "set", "value": 1}, "hazard"),
        ({"hazard": "flood", "mode": "add", "value": 1}, "mode"),
        ({"hazard": "flood", "mode": "set", "value": -1}, "negative"),
    ],
)
def test_impossible_weight_changes_are_refused(change, message):
    with pytest.raises(ValueError, match=message):
        apply_weight_changes(CONFIG.weights, [change])


# --- real figures --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hub, hazard, expected",
    [
        # Each recounted on 2026-11-24 by an independent script that marks covered minutes
        # straight from the database, without this package's code.
        ("MSP", "winter", 2.71),
        ("DEN", "winter", 2.07),
        ("DAL", "severe_storm", 0.39),
        ("IAH", "flood", 0.47),
        ("MEM", "flood", 0.73),
    ],
)
def test_real_figures_match_the_independent_recount(real_data, hub, expected, hazard):
    score = score_hub(hub, real_data.hubs[hub].tz, real_data.warnings[hub], real_data.fema[hub], CONFIG, CONFIG.weights)
    assert round(score.hazards[hazard].rate, 2) == expected
