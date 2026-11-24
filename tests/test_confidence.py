"""Confidence labels: coverage, separation, weight stability (plan section 5.6, ASSUMPTIONS milestone 2 point 10)."""

import math
from datetime import UTC, datetime
from pathlib import Path

import pytest

from wra.ingest.iem import WarningEvent
from wra.scoring.confidence import (
    Gap,
    daily_confidence,
    decide,
    gap_test,
    stability,
    standard_error,
    warning_years_covered,
)
from wra.scoring.config import load_scoring_config
from wra.scoring.kpi import HazardFigure, HubScore, reweigh

CONFIG = load_scoring_config(Path(__file__).resolve().parents[1] / "config" / "scoring.toml")
RULES = CONFIG.confidence
NAMES = {"A": "Alpha", "B": "Bravo", "C": "Charlie", "D": "Delta"}


def hub(hub_id: str, winter: float, hurricane: float = 0.0, swing: float = 0.0) -> HubScore:
    """A hub whose winter days alternate around `winter` by +/- `swing` over ten years."""
    yearly = {2016 + i: winter + (swing if i % 2 else -swing) for i in range(10)}
    zero = {year: 0.0 for year in yearly}
    return HubScore(
        hub_id,
        {
            "winter": HazardFigure("winter", winter, 1.0, winter, yearly),
            "flood": HazardFigure("flood", 0.0, 1.0, 0.0, zero),
            "severe_storm": HazardFigure("severe_storm", 0.0, 1.0, 0.0, zero),
            "hurricane": HazardFigure("hurricane", hurricane, 5.0, hurricane * 5.0, None),
        },
    )


# --- separation ----------------------------------------------------------------------------


def test_standard_error_is_the_spread_of_the_yearly_figures_over_root_n():
    assert standard_error({2016: 1.0, 2017: 2.0, 2018: 3.0, 2019: 4.0}) == pytest.approx(1.2909944 / 2)
    assert standard_error(None) is None


def test_a_gap_passes_only_when_larger_than_the_combined_standard_error():
    a, b = hub("A", 3.0, swing=1.0), hub("B", 1.0, swing=1.0)
    noise = math.hypot(standard_error(a.yearly_edd("winter")), standard_error(b.yearly_edd("winter")))
    gap = gap_test(a, b, "winter")
    assert (gap.upper, gap.lower, gap.gap) == ("A", "B", pytest.approx(2.0))
    assert gap.noise == pytest.approx(noise)
    assert gap.passed is (2.0 > noise)
    assert gap_test(hub("A", 1.0, swing=1.0), hub("B", 1.0, swing=1.0), "winter").passed is False  # a tie fails


def test_hurricane_gaps_cannot_be_tested():
    assert gap_test(hub("A", 0, hurricane=0.3), hub("B", 0, hurricane=0.1), "hurricane").passed is None


def test_overall_noise_comes_from_the_warning_years_only():
    # The hurricane figure is the same in every year, so it adds nothing to the swing.
    with_hurricane = gap_test(hub("A", 2.0, hurricane=0.3, swing=0.5), hub("B", 1.0, swing=0.5), "overall")
    without = gap_test(hub("A", 2.0, swing=0.5), hub("B", 1.0, swing=0.5), "overall")
    assert with_hurricane.noise == pytest.approx(without.noise)


# --- the label -----------------------------------------------------------------------------


def passed(a: str = "A", b: str = "B") -> Gap:
    return Gap(a, b, 1.0, 0.1)


def failed(a: str = "A", b: str = "B") -> Gap:
    return Gap(a, b, 0.1, 1.0)


def untestable(a: str = "A", b: str = "B") -> Gap:
    return Gap(a, b, 1.0, None)


def test_high_needs_full_coverage_and_every_gap_clear():
    result = decide(1.0, [passed(), passed("B", "C")], RULES, NAMES)
    assert result.label == "high"
    assert "Every gap" in result.reason


def test_more_than_half_the_gaps_failing_is_low_and_the_reason_names_the_ones_that_hold():
    result = decide(1.0, [passed("A", "B"), failed("B", "C"), failed("C", "D")], RULES, NAMES)
    assert result.label == "low"
    assert "2 of 3" in result.reason and "Alpha above Bravo" in result.reason


def test_half_the_gaps_failing_is_medium():
    assert decide(1.0, [passed(), failed("B", "C")], RULES, NAMES).label == "medium"


def test_coverage_sets_the_floor_and_the_ceiling():
    assert decide(0.95, [passed()], RULES, NAMES).label == "medium"
    assert decide(0.89, [passed()], RULES, NAMES).label == "low"


def test_an_untestable_hurricane_gap_caps_the_label_at_medium():
    result = decide(1.0, [untestable()], RULES, NAMES)
    assert result.label == "medium"
    assert "one long-run FEMA figure" in result.reason


def test_no_gaps_at_all_rests_on_coverage():
    assert decide(1.0, [], RULES, NAMES).label == "high"


# --- weight stability ----------------------------------------------------------------------


def test_a_ranking_whose_top_survives_every_variant_is_stable():
    scores = {h.hub_id: h for h in (hub("A", 5.0), hub("B", 2.0), hub("C", 1.0), hub("D", 0.5))}
    result = stability(scores, "overall", list(scores), CONFIG.weights, RULES)
    assert result.same_top_hub and result.same_top_set
    assert len(result.variants) == 8
    assert decide(1.0, [passed()], RULES, NAMES, result).label == "high"


def test_a_top_hub_that_changes_when_a_weight_doubles_makes_the_label_low():
    # A leads on winter; B's hurricane figure overtakes it once hurricanes count double.
    scores = {h.hub_id: h for h in (hub("A", 3.0), hub("B", 0.0, hurricane=0.5), hub("C", 0.1), hub("D", 0.0))}
    result = stability(scores, "overall", list(scores), CONFIG.weights, RULES)
    assert not result.same_top_hub
    assert result.top_with("hurricane", 2.0) == ["B", "A", "C"]
    verdict = decide(1.0, [passed()], RULES, NAMES, result)
    assert verdict.label == "low" and "hurricane" in verdict.reason


def test_reweighing_scales_the_figures_without_recounting():
    score = reweigh(hub("A", 2.0, hurricane=0.2), {"winter": 1.5, "flood": 1.0, "severe_storm": 1.0, "hurricane": 10.0})
    assert score.hazards["winter"].edd == pytest.approx(3.0)
    assert score.hazards["hurricane"].edd == pytest.approx(2.0)
    assert score.yearly_edd("winter")[2016] == pytest.approx(3.0)


# --- coverage ------------------------------------------------------------------------------


def _row(issue: str, expire: str) -> WarningEvent:
    return WarningEvent(
        "zone", "MPX", 2017, "WW", "Y", 1, "MNZ060",
        datetime.fromisoformat(issue).replace(tzinfo=UTC), datetime.fromisoformat(expire).replace(tzinfo=UTC), "x",
    )  # fmt: skip


def test_a_year_counts_as_covered_when_the_archive_holds_any_row_in_it():
    rows = [_row("2017-01-10T00:00", "2017-01-11T00:00"), _row("2018-12-31T23:00", "2019-01-01T08:00")]
    # The second row starts on 31 Dec 2018 in Chicago and runs into 2019 there: both years covered.
    assert warning_years_covered(rows, "America/Chicago", 2016, 2019) == 3


# --- station statistics --------------------------------------------------------------------


@pytest.mark.parametrize("missing, total, label", [(1, 365, "high"), (7, 365, "high"), (8, 365, "medium"), (37, 365, "low")])
def test_station_confidence_follows_the_share_of_missing_days(missing, total, label):
    result = daily_confidence(missing, total, CONFIG.daily)
    assert result.label == label
    assert f"{missing} of {total} days missing" in result.reason
