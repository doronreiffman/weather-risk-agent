"""The checks a final answer must pass before anyone sees it (plan section 8.4, and the owner's
additions of 2026-11-24 after the milestone 3 review).

1. Every evidence id is a real result from this conversation; an answered question cites at least one
   result that succeeded, so the page has a table, a period and a confidence to show.
2. hubs_ranked is the top of a cited ranking, comparison or explanation, or its bottom when the answer
   says its hubs come from the bottom (hubs_from).
3. is_what_if is true exactly when a cited result is a what-if.
4. Grounding: every number in digits in the verdict and caveats is in the cited results, their
   arguments, or the facts the system prompt states (the period, FEMA's record, the number of hubs).
5. Bands: in each sentence of the verdict, the first band named after a hub, before the next hub is
   named, must be that hub's cited band (owner, 2026-11-24, replacing "first band, first hub").
6. Shape: no Markdown table in the verdict (tables come from code), at most three caveats.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from wra.agent.grounding import ungrounded
from wra.agent.schemas import FinalAnswer, ToolCallRecord
from wra.scoring.config import BAND_LABELS
from wra.tools.envelope import ToolResult

MAX_CAVEATS = 3
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", flags=re.MULTILINE)


@dataclass(frozen=True)
class CitedResult:
    result_id: str
    call: ToolCallRecord
    result: ToolResult


def check_answer(
    answer: FinalAnswer,
    results: dict[str, CitedResult],
    prompt_facts: Iterable[float] = (),
    hub_names: Mapping[str, str] | None = None,
) -> list[str]:
    problems = []
    unknown = [e for e in answer.evidence if e not in results]
    if unknown:
        problems.append(f"evidence cites result ids that do not exist: {unknown}; the results are {list(results)}")
    cited = [results[e] for e in dict.fromkeys(answer.evidence) if e in results]
    if answer.status == "answered" and not any(r.result.ok for r in cited):
        problems.append('status is "answered" but no cited result succeeded; cite the results the verdict rests on')

    if answer.hubs_ranked:
        orders = _orders(cited)
        if not any(_fits(answer.hubs_ranked, answer.hubs_from, o) for o in orders):
            problems.append(
                f"hubs_ranked {answer.hubs_ranked} is not the {answer.hubs_from} of any cited order "
                f"({[o.hubs for o in orders] or 'none of the cited results ranks hubs'})"
            )

    what_if = any(r.result.ok and r.result.provenance.is_what_if for r in cited)
    if answer.is_what_if != what_if:
        problems.append(f"is_what_if is {answer.is_what_if}, but the cited results {'are' if what_if else 'are not'} a what-if")

    text = " ".join([answer.verdict, *answer.caveats])
    missing = ungrounded(text, [r.result.model_dump() for r in cited], [r.call.input for r in cited] + list(prompt_facts))
    if missing:
        problems.append(
            f"these numbers are not in the cited results or their arguments: {missing}; use only figures "
            "from the results you cite, or cite the result that holds them"
        )

    if hub_names:
        problems += _band_problems(answer.verdict, cited, hub_names)

    if len(_TABLE_ROW.findall(answer.verdict)) >= 2:
        problems.append("the verdict contains a table; the page shows the cited results' tables, so write prose only")
    if len(answer.caveats) > MAX_CAVEATS:
        problems.append(f"{len(answer.caveats)} caveats; give at most {MAX_CAVEATS}")
    return problems


def band_mentions(text: str) -> list[tuple[int, str]]:
    """Band labels in the text, in order, written as the tools write them, capitalised. "High" inside
    "Very high" is not High; "Low confidence" is the confidence label, not a band."""
    found = []
    for label in BAND_LABELS:
        pattern = rf"(?<![\w])(?<!Very ){re.escape(label)}(?![\w])"
        if label == "Low":
            pattern += r"(?! confidence)"
        found += [(m.start(), label) for m in re.finditer(pattern, text)]
    return sorted(found)


def first_band(text: str) -> str | None:
    mentions = band_mentions(text)
    return mentions[0][1] if mentions else None


def _band_problems(verdict: str, cited: list[CitedResult], hub_names: Mapping[str, str]) -> list[str]:
    bands, problems = _cited_bands(cited), []
    for sentence in re.split(r"(?<=[.!?])\s+", verdict):
        hubs = _hub_mentions(sentence, hub_names)
        labels = band_mentions(sentence)
        for i, (start, hub) in enumerate(hubs):
            end = hubs[i + 1][0] if i + 1 < len(hubs) else len(sentence)
            named = next((label for pos, label in labels if start < pos < end), None)
            if named is None:
                continue
            if hub not in bands:
                problems.append(f"the verdict calls {hub_names[hub]} {named!r}, but no cited result gives its band; "
                                "cite one that does")  # fmt: skip
            elif named not in bands[hub]:
                cited = " or ".join(repr(b) for b in bands[hub])
                problems.append(f"the verdict calls {hub_names[hub]} {named!r}, but the cited band is {cited}")
    return problems


def _hub_mentions(text: str, hub_names: Mapping[str, str]) -> list[tuple[int, str]]:
    """Each place a hub is named, by city or id, in order. "Minneapolis (MSP)" counts once."""
    found = []
    for hub, city in hub_names.items():
        for word in (city, hub):
            found += [(m.start(), hub) for m in re.finditer(rf"(?<![\w]){re.escape(word)}(?![\w])", text)]
    found.sort()
    merged = []
    for pos, hub in found:
        if not merged or merged[-1][1] != hub:
            merged.append((pos, hub))
    return merged


def _cited_bands(cited: list[CitedResult]) -> dict[str, list[str]]:
    """Every band the cited results give each hub. An answer citing a what-if and the official ranking has
    two for a hub that moves; either may be named (owner, 2026-11-25, after Haiku's right what-if answers
    were refused when the last result cited overwrote the first)."""
    bands: dict[str, list[str]] = {}

    def add(hub: str, band: str | None) -> None:
        if band and band not in bands.setdefault(hub, []):
            bands[hub].append(band)

    for r in cited:
        if not r.result.ok:
            continue
        data = r.result.data
        if r.call.name == "explain_hub":
            add(data["hub_id"], data.get("band"))
        elif r.call.name == "rank_hubs" and data["hazard"] == "overall":  # a what-if's bands too
            for row in data["rows"]:
                add(row["hub_id"], row.get("band"))
        elif r.call.name == "compare_hubs":
            for row in data["results"].get("overall", []):
                add(row["hub_id"], row.get("band"))
    return bands


@dataclass(frozen=True)
class _Order:
    hubs: list[str]
    has_bottom: bool  # False when the ranking was cut at top_n: its last row is not the least exposed
    must_include: str | None = None  # an explanation's order is about this hub


def _orders(cited: list[CitedResult]) -> list[_Order]:
    orders = []
    for r in cited:
        if not r.result.ok:
            continue
        data = r.result.data
        if r.call.name == "rank_hubs":
            orders.append(_Order([row["hub_id"] for row in data["rows"]], has_bottom=data["top_n"] is None))
        elif r.call.name == "compare_hubs":
            orders += [_Order([row["hub_id"] for row in rows], True) for rows in data["results"].values()]
        elif r.call.name == "explain_hub":
            hubs = [h for h in (data["above"] and data["above"]["hub_id"], data["hub_id"],
                                data["below"] and data["below"]["hub_id"]) if h]  # fmt: skip
            orders.append(_Order(hubs, True, must_include=data["hub_id"]))
    return orders


def _fits(hubs: list[str], end: str, order: _Order) -> bool:
    if order.must_include and order.must_include not in hubs:
        return False
    if end == "top":
        return order.hubs[: len(hubs)] == hubs
    return order.has_bottom and len(hubs) <= len(order.hubs) and order.hubs[len(order.hubs) - len(hubs) :] == hubs
