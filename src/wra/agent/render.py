"""Build the reply the page shows: the model's verdict, plus the tables and the footnote taken
directly from the cited tool results (plan section 7.1, step 8). The model never types a table."""

from wra.agent.checks import CitedResult
from wra.agent.schemas import AgentReply, FinalAnswer, Footnote, Trace
from wra.tools.envelope import Provenance

_RANK = {"low": 0, "medium": 1, "high": 2}


def render(session_id: str, answer: FinalAnswer, results: dict[str, CitedResult], trace: Trace) -> AgentReply:
    cited = [results[e] for e in dict.fromkeys(answer.evidence) if e in results]
    shown = [r.result for r in cited if r.result.ok]
    return AgentReply(
        session_id=session_id,
        status=answer.status,
        verdict=answer.verdict,
        tables=[r.display for r in shown if r.display is not None],
        footnote=footnote([(r.display.title if r.display else r.tool, r.provenance) for r in shown
                           if r.provenance is not None]),  # fmt: skip
        caveats=answer.caveats,
        hubs_ranked=answer.hubs_ranked,
        is_what_if=answer.is_what_if,
        evidence=list(dict.fromkeys(answer.evidence)),
        hazard_orders=answer.hazard_orders,
        trace=trace,
    )


def footnote(cited: list[tuple[str, Provenance]]) -> Footnote | None:
    """One footnote for several results: every source, every period once, the latest data date, and the
    lowest confidence with its reason. When several results give that label, each reason is led by its
    table's name, so two tables' reasons do not read as one (review, 2026-11-25)."""
    if not cited:
        return None
    provenances = [p for _, p in cited]
    lowest = min(provenances, key=lambda p: _RANK[p.confidence])
    reasons = dict.fromkeys((title.split(":")[0], p.confidence_reason) for title, p in cited
                            if p.confidence == lowest.confidence)  # fmt: skip
    distinct = list(dict.fromkeys(reason for _, reason in reasons))
    reason = distinct[0] if len(distinct) == 1 else " ".join(f"{name}: {text}" for name, text in reasons)
    periods = [part for p in provenances for part in p.period.split("; ")]
    return Footnote(
        sources=list(dict.fromkeys(s for p in provenances for s in p.sources)),
        period="; ".join(dict.fromkeys(periods)),
        data_as_of=max(p.data_as_of for p in provenances),
        confidence=lowest.confidence,
        confidence_reason=reason,
    )
