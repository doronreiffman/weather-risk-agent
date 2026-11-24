"""The checks a final answer must pass before anyone sees it (plan section 8.4, and the owner's
additions of 2026-11-24 after the milestone 3 review).

1. Every evidence id is a real result from this conversation; an answered question cites at least one
   result that succeeded, so the page has a table, a period and a confidence to show.
2. hubs_ranked is the top of a cited ranking, comparison or explanation, or its bottom when the answer
   says its hubs come from the bottom (hubs_from).
3. is_what_if is true exactly when a cited result is a what-if.
4. Grounding: every number in digits in the verdict and caveats is in the cited results, their
   arguments, or the facts the system prompt states (the period, FEMA's record, the number of hubs).
5. If the verdict names a band, the first band it names is the cited band of the first hub it names.
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
        fits = _is_top if answer.hubs_from == "top" else _is_bottom
        if not any(fits(answer.hubs_ranked, order) for order in orders):
            problems.append(
                f"hubs_ranked {answer.hubs_ranked} is not the {answer.hubs_from} of any cited order "
                f"({orders or 'none of the cited results ranks hubs'})"
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


def first_band(text: str) -> str | None:
    """The first band label in the text, written as the tools write it, capitalised. "High" inside
    "Very high" is not High; "Low confidence" is the confidence label, not a band."""
    first = None
    for label in BAND_LABELS:
        pattern = rf"(?<![\w])(?<!Very ){re.escape(label)}(?![\w])"
        if label == "Low":
            pattern += r"(?! confidence)"
        match = re.search(pattern, text)
        if match and (first is None or match.start() < first[0]):
            first = (match.start(), label)
    return first[1] if first else None


def _band_problems(verdict: str, cited: list[CitedResult], hub_names: Mapping[str, str]) -> list[str]:
    named = first_band(verdict)
    if named is None:
        return []
    hub = _first_hub(verdict, hub_names)
    if hub is None:
        return []
    bands = _cited_bands(cited)
    if hub not in bands:
        return [f"the verdict calls {hub_names[hub]} {named!r}, but no cited result gives its band; cite one that does"]
    if bands[hub] != named:
        return [f"the verdict calls {hub_names[hub]} {named!r}, but the cited band is {bands[hub]!r}"]
    return []


def _first_hub(text: str, hub_names: Mapping[str, str]) -> str | None:
    first = None
    for hub, city in hub_names.items():
        for word in (city, hub):
            match = re.search(rf"(?<![\w]){re.escape(word)}(?![\w])", text)
            if match and (first is None or match.start() < first[0]):
                first = (match.start(), hub)
    return first[1] if first else None


def _cited_bands(cited: list[CitedResult]) -> dict[str, str]:
    bands = {}
    for r in cited:
        if not r.result.ok:
            continue
        data = r.result.data
        if r.call.name == "explain_hub" and data.get("band"):
            bands[data["hub_id"]] = data["band"]
        elif r.call.name == "rank_hubs" and data["hazard"] == "overall":  # a what-if's bands too
            bands.update({row["hub_id"]: row["band"] for row in data["rows"] if row.get("band")})
        elif r.call.name == "compare_hubs":
            bands.update({row["hub_id"]: row["band"] for row in data["results"].get("overall", []) if row.get("band")})
    return bands


def _orders(cited: list[CitedResult]) -> list[list[str]]:
    orders = []
    for r in cited:
        if not r.result.ok:
            continue
        data = r.result.data
        if r.call.name == "rank_hubs":
            orders.append([row["hub_id"] for row in data["rows"]])
        elif r.call.name == "compare_hubs":
            orders += [[row["hub_id"] for row in rows] for rows in data["results"].values()]
        elif r.call.name == "explain_hub":
            orders.append([h for h in (data["above"] and data["above"]["hub_id"], data["hub_id"],
                                       data["below"] and data["below"]["hub_id"]) if h])  # fmt: skip
    return orders


def _is_top(hubs: list[str], order: list[str]) -> bool:
    return order[: len(hubs)] == hubs


def _is_bottom(hubs: list[str], order: list[str]) -> bool:
    return len(hubs) <= len(order) and order[len(order) - len(hubs) :] == hubs
