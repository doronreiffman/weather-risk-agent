"""The score-change alert (docs/ALERT_DESIGN.md): the overall ranking as a snapshot, two snapshots compared, and the
issue's title and body written by code. Pure functions apart from current_snapshot, which runs the rank_hubs tool;
nothing here uses the network or a model."""

import hashlib
import json
from dataclasses import asdict, dataclass

from wra.scoring.config import HAZARDS
from wra.tools.context import ToolContext
from wra.tools.registry import run_tool

SCHEMA = 1
# The demo (design 5.6): the what-if evaluation case 7 expects the chat to make, so its figures match the chat's.
DEMO_CHANGES = [{"hazard": "hurricane", "mode": "multiply", "value": 2.0}]
ADVICE = "This says that figures differ, not why. A hiccup at a source can look like a change, so run the job again first."


@dataclass(frozen=True)
class HubScore:
    hub_id: str
    city: str  # "Miami"
    label: str  # "Miami (MIA)"
    rank: int
    value: float
    band: str
    hazards: dict[str, float]


@dataclass(frozen=True)
class Snapshot:
    hubs: dict[str, HubScore]
    confidence: str
    inputs: dict[str, object]  # weights, period, band_cutoffs, fema_release, data_as_of: reported, never a trigger


@dataclass(frozen=True)
class HubChange:
    hub_id: str
    city: str
    before: HubScore | None  # None: the hub was added
    after: HubScore | None  # None: the hub was removed


@dataclass(frozen=True)
class Difference:
    changed: list[HubChange]  # own figure, band or a hazard figure moved, or the hub was added or removed
    rank_only: list[HubChange]  # passed by others: rank moved, own figures did not
    confidence: tuple[str, str] | None
    inputs: dict[str, tuple[object, object]]
    hub_count: int  # hubs in either snapshot, for the title's "of 12 hubs"

    @property
    def is_empty(self) -> bool:
        return not self.changed and not self.rank_only and self.confidence is None


def current_snapshot(ctx: ToolContext, weight_changes: list[dict] | None = None) -> Snapshot:
    args = {"hazard": "overall", "region": "all", "top_n": None, "weight_changes": list(weight_changes or [])}
    result = run_tool(ctx, "rank_hubs", args)
    if not result.ok:
        raise RuntimeError(f"rank_hubs failed: {result.error.message}")
    hubs = {
        row["hub_id"]: HubScore(
            hub_id=row["hub_id"], city=row["city"], label=ctx.label(row["hub_id"]), rank=row["rank"],
            value=row["value"], band=row["band"], hazards=dict(row["breakdown"]),
        )  # fmt: skip
        for row in result.data["rows"]
    }
    cfg = ctx.config
    inputs = {
        "weights": dict(result.data["weights"]),
        "period": f"{cfg.first_year}-{cfg.last_year}",
        "band_cutoffs": list(cfg.band_cutoffs),
        "fema_release": ctx.data.fema_release,
        "data_as_of": ctx.data.data_as_of,
    }
    return Snapshot(hubs=hubs, confidence=result.provenance.confidence, inputs=inputs)


def to_json(s: Snapshot) -> str:
    """One hub per line, in rank order, so a diff of the committed file reads easily."""
    hubs = sorted(s.hubs.values(), key=lambda h: h.rank)
    lines = [
        "{",
        f'  "schema": {SCHEMA},',
        f'  "confidence": {json.dumps(s.confidence)},',
        f'  "inputs": {json.dumps(s.inputs, sort_keys=True)},',
        '  "hubs": [',
        *[f"    {json.dumps(asdict(h))}{',' if i < len(hubs) - 1 else ''}" for i, h in enumerate(hubs)],
        "  ]",
        "}",
    ]
    return "\n".join(lines) + "\n"


def from_json(text: str) -> Snapshot:
    """Raises ValueError for anything it cannot read, so the command can say so plainly."""
    data = json.loads(text)  # a JSONDecodeError is a ValueError
    try:
        if data.get("schema") != SCHEMA:
            raise ValueError(f"schema {data.get('schema')!r}, expected {SCHEMA}")
        hubs = {h["hub_id"]: HubScore(**h) for h in data["hubs"]}
        return Snapshot(hubs=hubs, confidence=data["confidence"], inputs=data["inputs"])
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"missing or malformed field: {error}") from error


def _shown(x: float) -> str:
    return f"{x:.2f}"


def _figures(h: HubScore) -> tuple:
    """What the ranking shows of a hub, rank aside: compared as shown, to two decimals."""
    return _shown(h.value), h.band, tuple(_shown(h.hazards[k]) for k in HAZARDS)


def compare(before: Snapshot, after: Snapshot) -> Difference:
    changed, rank_only = [], []
    for hub_id, a in sorted(after.hubs.items(), key=lambda item: item[1].rank):
        b = before.hubs.get(hub_id)
        if b is None or _figures(b) != _figures(a):
            changed.append(HubChange(hub_id, a.city, b, a))
        elif b.rank != a.rank:
            rank_only.append(HubChange(hub_id, a.city, b, a))
    for hub_id, b in sorted(before.hubs.items(), key=lambda item: item[1].rank):
        if hub_id not in after.hubs:
            changed.append(HubChange(hub_id, b.city, b, None))
    confidence = (before.confidence, after.confidence) if before.confidence != after.confidence else None
    keys = sorted(set(before.inputs) | set(after.inputs))
    inputs = {k: (before.inputs.get(k), after.inputs.get(k)) for k in keys if before.inputs.get(k) != after.inputs.get(k)}
    return Difference(changed, rank_only, confidence, inputs, len(set(before.hubs) | set(after.hubs)))


def change_id(diff: Difference, demo: bool = False) -> str:
    """The same differences give the same id. Inputs are left out, so a newer data date alone never makes a new one."""

    def hub(c: HubChange) -> dict:
        return {"hub_id": c.hub_id, "before": c.before and asdict(c.before), "after": c.after and asdict(c.after)}

    payload = {
        "changed": [hub(c) for c in diff.changed],
        "rank_only": [hub(c) for c in diff.rank_only],
        "confidence": list(diff.confidence) if diff.confidence else None,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
    return f"demo-{digest}" if demo else digest


def _moved(before, after, fmt=str) -> str:
    return fmt(after) if before == after else f"{fmt(before)} → {fmt(after)}"


def _row(c: HubChange, hazard_labels: dict[str, str]) -> str:
    b, a = c.before, c.after
    if b is None:
        return f"| {a.label} | {a.rank} (new) | {_shown(a.value)} | {a.band} | added |"
    if a is None:
        return f"| {b.label} | {b.rank} (removed) | {_shown(b.value)} | {b.band} | removed |"
    hazards = "; ".join(
        f"{hazard_labels[k]} {_shown(b.hazards[k])} → {_shown(a.hazards[k])}"
        for k in HAZARDS
        if _shown(b.hazards[k]) != _shown(a.hazards[k])
    )
    what = hazards or "too small to show per hazard"
    return f"| {a.label} | {_moved(b.rank, a.rank)} | {_moved(b.value, a.value, _shown)} | {_moved(b.band, a.band)} | {what} |"


def _number(x) -> str:
    return f"{x:g}" if isinstance(x, (int, float)) else str(x)


def _inputs_line(inputs: dict[str, tuple[object, object]]) -> str | None:
    parts = []
    for key, (b, a) in inputs.items():
        if key == "weights" and isinstance(b, dict) and isinstance(a, dict):
            parts += [
                f"{h.replace('_', ' ')} weight {_number(b.get(h))} → {_number(a.get(h))}"
                for h in sorted(set(b) | set(a))
                if b.get(h) != a.get(h)
            ]
        elif key == "band_cutoffs":
            parts.append(f"band cut-offs {', '.join(map(_number, b or []))} → {', '.join(map(_number, a or []))}")
        else:
            name = {"data_as_of": "data date", "fema_release": "FEMA release", "period": "period"}.get(key, key)
            parts.append(f"{name} {b} → {a}")
    return f"Inputs that differ: {'; '.join(parts)}." if parts else None


def _demo_banner(diff: Difference) -> str:
    weights = diff.inputs.get("weights")
    changes = []
    if weights and isinstance(weights[0], dict) and isinstance(weights[1], dict):
        b, a = weights
        changes = [
            f"the {h.replace('_', ' ')} weight was {_number(a[h])} instead of {_number(b[h])}" for h in sorted(a) if a[h] != b.get(h)
        ]  # fmt: skip
    what = " and ".join(changes) or "the weights were changed"
    return (
        "**This is a demonstration, not a real change.** The official scores have not moved. "
        f"For this run only, {what}, on the data committed in the repository."
    )


def message(diff: Difference, hazard_labels: dict[str, str], demo: bool = False) -> tuple[str, str]:
    """The issue's title and Markdown body. The table names hubs by label, the rank-only line by city."""
    total = diff.hub_count
    if diff.changed:
        bands = sum(1 for c in diff.changed if c.before and c.after and c.before.band != c.after.band)
        title = f"Hub risk scores changed: {len(diff.changed)} of {total} hubs, {bands} changed band"
    elif diff.rank_only:
        title = f"Hub risk ranking changed: {len(diff.rank_only)} of {total} hubs moved in rank"
    else:
        title = f"Hub risk ranking's confidence changed: {diff.confidence[0]} → {diff.confidence[1]}"
    if demo:
        title = f"[DEMO] {title}"

    parts = []
    if demo:
        parts.append(_demo_banner(diff))
    if diff.changed:
        table = ["| Hub | Rank | Disruption days a year | Band | What moved |", "|---|---|---|---|---|"]
        table += [_row(c, hazard_labels) for c in diff.changed]
        parts.append("\n".join(table))
    notes = []
    if diff.rank_only:
        moves = ", ".join(f"{c.city} {c.before.rank} → {c.after.rank}" for c in diff.rank_only)
        notes.append(f"Rank only, own figures unchanged: {moves}.")
    if diff.confidence:
        notes.append(f"Confidence in the ranking: {diff.confidence[0]} → {diff.confidence[1]}.")
    if line := _inputs_line(diff.inputs):
        notes.append(line)
    if notes:
        parts.append("\n".join(notes))
    advice = [ADVICE]
    if demo:
        advice.append("Nothing needs accepting after a demo: close this issue.")
    else:
        advice.append(
            "If it repeats, run `uv run wra ingest --refresh` and `uv run wra rank overall` locally. If the new "
            "ranking is right, run `uv run wra alert --accept`, commit `data/raw/` with `data/reviewed_scores.json`, "
            "push and close this issue."
        )
    parts.append(" ".join(advice))
    parts.append(f"Change id: {change_id(diff, demo)}")
    return title, "\n\n".join(parts) + "\n"
