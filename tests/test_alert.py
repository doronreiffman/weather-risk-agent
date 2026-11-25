"""The score-change alert (docs/ALERT_DESIGN.md, docs/ALERT_PLAN.md): snapshots, the comparison, the message."""

import re
from dataclasses import replace

import pytest

from conftest import REPO
from wra.alert import (
    DEMO_CHANGES,
    HubScore,
    Snapshot,
    change_id,
    compare,
    current_snapshot,
    from_json,
    message,
    to_json,
)

LABELS = {"winter": "Winter weather", "flood": "Flooding", "severe_storm": "Severe storms", "hurricane": "Hurricanes"}
INPUTS = {
    "weights": {"winter": 1.0, "flood": 1.0, "severe_storm": 1.0, "hurricane": 5.0},
    "period": "2016-2025",
    "band_cutoffs": [1.0, 2.0, 3.0],
    "fema_release": "December 2025",
    "data_as_of": "2026-11-24",
}
DEMO_BANNER = (
    "**This is a demonstration, not a real change.** The official scores have not moved. For this run only, "
    "the hurricane weight was 10 instead of 5, on the data committed in the repository."
)


def hub(hub_id, city, rank, value, band, winter=0.0, flood=0.0, severe=0.0, hurricane=0.0) -> HubScore:
    return HubScore(
        hub_id=hub_id, city=city, label=f"{city} ({hub_id})", rank=rank, value=value, band=band,
        hazards={"winter": winter, "flood": flood, "severe_storm": severe, "hurricane": hurricane},
    )  # fmt: skip


MSP = hub("MSP", "Minneapolis", 1, 2.90, "High", winter=2.71, flood=0.06, severe=0.13)
IAH = hub("IAH", "Houston", 2, 1.96, "Moderate", winter=0.39, flood=0.47, severe=0.19, hurricane=0.92)
ATL = hub("ATL", "Atlanta", 3, 1.24, "Moderate", winter=0.27, flood=0.56, severe=0.17, hurricane=0.24)
CMH = hub("CMH", "Columbus", 4, 0.99, "Low", winter=0.66, flood=0.13, severe=0.17, hurricane=0.03)


def snap(hubs=(MSP, IAH, ATL, CMH), confidence="low", **inputs) -> Snapshot:
    return Snapshot(hubs={h.hub_id: h for h in hubs}, confidence=confidence, inputs={**INPUTS, **inputs})


def ids(changes) -> list[str]:
    return [c.hub_id for c in changes]


def with_hazard(h: HubScore, **changes) -> HubScore:
    hazards = {**h.hazards, **{k: v for k, v in changes.items() if k in h.hazards}}
    rest = {k: v for k, v in changes.items() if k not in h.hazards}
    return replace(h, hazards=hazards, **rest)


FLOOD_UP = snap(hubs=(MSP, with_hazard(IAH, flood=0.52, value=2.01), ATL, CMH))


def test_no_change_is_empty():
    diff = compare(snap(), snap())
    assert diff.is_empty
    assert diff.changed == [] and diff.rank_only == [] and diff.inputs == {}


def test_one_figure_change_is_listed():
    diff = compare(snap(), FLOOD_UP)
    assert ids(diff.changed) == ["IAH"]
    assert diff.rank_only == []
    assert not diff.is_empty


def test_a_rank_swap_lists_the_mover_and_the_passed():
    after = snap(hubs=(MSP, with_hazard(ATL, rank=2, value=2.00, flood=1.32), replace(IAH, rank=3), CMH))
    diff = compare(snap(), after)
    assert ids(diff.changed) == ["ATL"]
    assert ids(diff.rank_only) == ["IAH"]


def test_a_band_crossing_is_a_change():
    diff = compare(snap(), snap(hubs=(MSP, IAH, ATL, replace(CMH, value=1.00, band="Moderate"))))
    assert ids(diff.changed) == ["CMH"]


def test_the_confidence_label_change_is_reported():
    diff = compare(snap(), snap(confidence="medium"))
    assert diff.confidence == ("low", "medium")
    assert not diff.is_empty
    assert diff.changed == [] and diff.rank_only == []
    title, _ = message(diff, LABELS)
    assert title == "Hub risk ranking's confidence changed: low → medium"


def test_a_hub_added_or_removed_is_a_change():
    phx = hub("PHX", "Phoenix", 4, 0.42, "Low", flood=0.17, severe=0.20, hurricane=0.06)
    diff = compare(snap(), snap(hubs=(MSP, IAH, ATL, phx)))
    assert ids(diff.changed) == ["PHX", "CMH"]
    added, removed = diff.changed
    assert added.before is None and added.after == phx
    assert removed.before == CMH and removed.after is None


def test_inputs_alone_are_not_a_change():
    diff = compare(snap(), snap(data_as_of="2026-12-02"))
    assert diff.is_empty
    assert diff.inputs == {"data_as_of": ("2026-11-24", "2026-12-02")}


def test_change_id_ignores_the_data_date():
    first = compare(snap(), FLOOD_UP)
    a_week_later = compare(snap(), replace(FLOOD_UP, inputs={**INPUTS, "data_as_of": "2026-12-02"}))
    other = compare(snap(), snap(hubs=(MSP, IAH, ATL, replace(CMH, value=1.00, band="Moderate"))))
    assert re.fullmatch(r"[0-9a-f]{12}", change_id(first))
    assert change_id(first) == change_id(a_week_later)
    assert change_id(first) != change_id(other)
    assert re.fullmatch(r"demo-[0-9a-f]{12}", change_id(first, demo=True))


def test_message_shows_an_unchanged_rank_once():
    diff = compare(snap(), snap(hubs=(MSP, IAH, with_hazard(ATL, value=1.48, hurricane=0.49), CMH)))
    _, body = message(diff, LABELS)
    assert "| Atlanta (ATL) | 3 | 1.24 → 1.48 | Moderate | Hurricanes 0.24 → 0.49 |" in body
    assert "3 → 3" not in body


def test_message_copes_with_a_change_too_small_to_show_per_hazard():
    diff = compare(snap(), snap(hubs=(MSP, IAH, ATL, replace(CMH, value=1.00, band="Moderate"))))
    _, body = message(diff, LABELS)
    assert "| Columbus (CMH) | 4 | 0.99 → 1.00 | Low → Moderate | too small to show per hazard |" in body


def test_snapshot_round_trips_through_json():
    s = snap()
    text = to_json(s)
    assert from_json(text) == s
    assert text.endswith("\n")
    hub_lines = [line for line in text.splitlines() if '"hub_id"' in line]
    assert len(hub_lines) == len(s.hubs)
    assert all(line.count('"hub_id"') == 1 for line in hub_lines)


@pytest.mark.parametrize("text", ["{", '{"schema": 2}', '{"schema": 1, "confidence": "low"}', "[]"])
def test_from_json_rejects_what_it_cannot_read(text):
    with pytest.raises(ValueError):
        from_json(text)


def test_the_real_title_has_no_demo_mark():
    title, body = message(compare(snap(), FLOOD_UP), LABELS)
    assert title == "Hub risk scores changed: 1 of 4 hubs, 0 changed band"
    assert "demonstration" not in body
    assert body.rstrip().endswith(f"Change id: {change_id(compare(snap(), FLOOD_UP))}")


def test_the_demo_on_the_committed_data(real_db):
    from wra.tools.context import load_context

    ctx = load_context(real_db, REPO / "config" / "scoring.toml")
    diff = compare(current_snapshot(ctx), current_snapshot(ctx, DEMO_CHANGES))
    assert len(diff.changed) == 9
    assert sorted(c.hub_id for c in diff.changed if c.before.band != c.after.band) == ["CMH", "IAH", "MIA"]
    assert ids(diff.rank_only) == ["MSP", "DEN", "MCI"]

    title, body = message(diff, LABELS, demo=True)
    assert title == "[DEMO] Hub risk scores changed: 9 of 12 hubs, 3 changed band"
    assert body.startswith(DEMO_BANNER)
    assert "| Miami (MIA) | 8 → 1 | 1.85 → 3.37 | Moderate → Very high | Hurricanes 1.52 → 3.05 |" in body
    assert "Rank only, own figures unchanged: Minneapolis 1 → 2, Denver 3 → 5, Kansas City 4 → 6." in body
    assert "hurricane weight 5 → 10" in body
    assert "This says that figures differ, not why. A hiccup at a source can look like a change, so run the job again first." in body
    assert re.search(r"Change id: demo-[0-9a-f]{12}\n?$", body)
