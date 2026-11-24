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
        footnote=footnote([r.provenance for r in shown if r.provenance is not None]),
        caveats=answer.caveats,
        hubs_ranked=answer.hubs_ranked,
        is_what_if=answer.is_what_if,
        trace=trace,
    )


def footnote(provenances: list[Provenance]) -> Footnote | None:
    """One footnote for several results: every source, every period, the latest data date, and the
    lowest confidence with its reason."""
    if not provenances:
        return None
    lowest = min(provenances, key=lambda p: _RANK[p.confidence])
    reasons = list(dict.fromkeys(p.confidence_reason for p in provenances if p.confidence == lowest.confidence))
    return Footnote(
        sources=list(dict.fromkeys(s for p in provenances for s in p.sources)),
        period="; ".join(dict.fromkeys(p.period for p in provenances)),
        data_as_of=max(p.data_as_of for p in provenances),
        confidence=lowest.confidence,
        confidence_reason=" ".join(reasons),
    )
