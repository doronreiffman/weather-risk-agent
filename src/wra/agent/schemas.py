"""What an agent returns for one message: the shape the API sends and the evaluation grades.

Plan section 8.5, with three additions the graders need (Deviations, milestone 2):
`hubs_ranked` and `is_what_if` from the model's final answer (section 8.3), and
the status `no_data` for a question we cover about a period our data does not
(owner, 2026-11-24).
"""

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from wra.tools.envelope import Display

Status = Literal["answered", "out_of_scope", "no_data", "needs_clarification", "error"]
# Why a reply is an error. The API sends busy as 409, unknown_conversation as 404 and the model-side
# failures as 502 (owner, milestone 4), and internal_error, a bug in our own code, as 500. The message in
# `error` is for people, the code for programs.
ErrorCode = Literal["busy", "unknown_conversation", "model_call_failed", "time_limit", "declined", "cut_off",
                    "invalid_twice", "too_many_calls", "internal_error"]  # fmt: skip


class FinalAnswer(BaseModel):
    """What the model returns when it is done (plan section 8.3), requested through structured output."""

    model_config = ConfigDict(extra="forbid")
    status: Literal["answered", "out_of_scope", "no_data", "needs_clarification"]
    verdict: str  # one to four sentences of Markdown, no tables
    evidence: list[str]  # result ids (R1, R2, ...) whose tables the page shows, in order
    hubs_ranked: list[str]  # the order the verdict asserts, most exposed first; empty if none
    hubs_from: Literal["top", "bottom"]  # which end of the cited order those hubs come from
    is_what_if: bool
    caveats: list[str]  # zero to three short sentences


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    input: dict[str, Any]


class Trace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str
    tool_calls: list[ToolCallRecord] = []
    repaired: bool = False
    repair_problems: list[str] = []  # what the first answer failed, when it was repaired
    rejected_answer: str | None = None  # that first answer, as the model wrote it
    latency_ms: int = 0
    usage: dict[str, Any] = {}


class Footnote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: list[str]
    period: str
    data_as_of: str
    confidence: Literal["high", "medium", "low"]
    confidence_reason: str


class AgentReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str
    status: Status
    verdict: str
    tables: list[Display] = []
    footnote: Footnote | None = None
    caveats: list[str] = []
    hubs_ranked: list[str] = []
    is_what_if: bool = False
    evidence: list[str] = []  # the result ids the answer cites; their tables are `tables`
    error: str | None = None  # a plain message when status is "error"
    error_code: ErrorCode | None = None  # which failure, when status is "error"
    trace: Trace


class Agent(Protocol):
    """Anything that answers one message in a conversation. session_id None starts a new one."""

    name: str

    def answer(self, session_id: str | None, message: str) -> AgentReply: ...
