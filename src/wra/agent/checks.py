"""The checks a final answer must pass before anyone sees it (plan section 8.4).

1. Every evidence id is a real result from this conversation; an answered question cites at least one.
2. hubs_ranked follows the order of a cited ranking, comparison or explanation.
3. is_what_if is true exactly when a cited result is a what-if.
4. Grounding: every number in digits in the verdict and caveats is in the cited results or their arguments.
"""

from dataclasses import dataclass

from wra.agent.grounding import ungrounded
from wra.agent.schemas import FinalAnswer, ToolCallRecord
from wra.tools.envelope import ToolResult


@dataclass(frozen=True)
class CitedResult:
    result_id: str
    call: ToolCallRecord
    result: ToolResult


def check_answer(answer: FinalAnswer, results: dict[str, CitedResult]) -> list[str]:
    problems = []
    unknown = [e for e in answer.evidence if e not in results]
    if unknown:
        problems.append(f"evidence cites result ids that do not exist: {unknown}; the results are {list(results)}")
    if answer.status == "answered" and not answer.evidence:
        problems.append('status is "answered" but evidence is empty; cite the results the verdict rests on')
    cited = [results[e] for e in dict.fromkeys(answer.evidence) if e in results]

    if answer.hubs_ranked:
        orders = _orders(cited)
        if not any(_in_order(answer.hubs_ranked, order) for order in orders):
            problems.append(
                f"hubs_ranked {answer.hubs_ranked} does not follow the order of any cited result "
                f"({orders or 'none of the cited results ranks hubs'})"
            )

    what_if = any(r.result.ok and r.result.provenance.is_what_if for r in cited)
    if answer.is_what_if != what_if:
        problems.append(f"is_what_if is {answer.is_what_if}, but the cited results {'are' if what_if else 'are not'} a what-if")

    text = " ".join([answer.verdict, *answer.caveats])
    missing = ungrounded(text, [r.result.model_dump() for r in cited], [r.call.input for r in cited])
    if missing:
        problems.append(
            f"these numbers are not in the cited results or their arguments: {missing}; use only figures "
            "from the results you cite, or cite the result that holds them"
        )
    return problems


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


def _in_order(hubs: list[str], order: list[str]) -> bool:
    if any(h not in order for h in hubs) or len(set(hubs)) != len(hubs):
        return False
    positions = [order.index(h) for h in hubs]
    return positions == sorted(positions)
