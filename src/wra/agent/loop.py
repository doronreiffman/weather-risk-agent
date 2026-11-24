"""The agent loop on the Anthropic Messages API (plan sections 7 and 8).

One user message: call Claude with the system prompt, the conversation, six strict tools and the
final-answer schema; run the tools it calls and send the results back; when it answers, validate the
answer in code (checks.py). One repair attempt if anything fails, then a clear error. At most
`max_model_calls` model calls per message, and all of them within `message_time_limit_seconds`: each
call waits at most its own timeout or the time left, and the loop, not the SDK, makes the one retry,
so a wait the API asks for cannot run past the limit. A refused or cut-off reply becomes an error.
Nothing unverified is shown.

The conversation is kept append-only, which Opus 5.5's thinking blocks require, with two exceptions
set by the API or by us:
- after a server-side fallback, the thinking and tool-call blocks before the response's final
  `fallback` block are left out when the turn is sent back, as the API's fallback rules say;
- a turn that ends in an error is removed whole, so the next question does not inherit a rejected
  answer or a repair message.
Each tool result is stamped with a short result id (R1, R2, ...) that the final answer cites as
evidence; the milestone 3 spike showed the model invents ids it cannot see.
"""

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import ValidationError

from wra.agent.checks import CitedResult, check_answer
from wra.agent.prompt import prompt_facts, system_prompt
from wra.agent.render import render
from wra.agent.schemas import AgentReply, FinalAnswer, ToolCallRecord, Trace
from wra.agent.settings import AgentSettings, load_settings
from wra.agent.tooldefs import final_answer_schema, tool_definitions
from wra.tools.context import ToolContext
from wra.tools.envelope import failure
from wra.tools.registry import run_tool

REPAIR = (
    "Your final answer failed these checks:\n- {problems}\nAnswer again with a corrected final answer object. "
    "You may call tools first if you need a result to cite."
)
USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
_BEFORE_FALLBACK_LEFT_OUT = {"thinking", "redacted_thinking", "tool_use", "server_tool_use"}


class ModelClient(Protocol):
    def create(self, **request: Any) -> Any: ...


class AnthropicClient:
    """The real client. The key comes from the environment, which `.env` fills via python-dotenv.
    The SDK's own retries are off: SDK 2.13.0 waits as long as a `retry-after` header asks, with no upper
    bound (anthropic/_base_client.py, _calculate_retry_timeout), so the loop retries instead (_call)."""

    def __init__(self, settings: AgentSettings) -> None:
        import anthropic
        from dotenv import load_dotenv

        from wra import paths

        load_dotenv(paths.root() / ".env")
        self._client = anthropic.Anthropic(timeout=settings.timeout_seconds, max_retries=0)

    def create(self, **request: Any) -> Any:
        return self._client.beta.messages.create(**request)


BUSY = "The last question in this conversation is still being answered. Send this one when it has finished."
UNKNOWN = ("This conversation is no longer on the server, probably because the server restarted. Your question "
           "was not sent; send it again to start a new conversation.")  # fmt: skip
FIRST_RETRY_PAUSE = 0.5  # seconds, the SDK's first back-off (anthropic/_constants.py, INITIAL_RETRY_DELAY)


class _Stop(Exception):
    """A model call ended the message without an error from the model's API itself."""

    def __init__(self, text: str, code: str) -> None:
        super().__init__(text)
        self.text, self.code = text, code


@dataclass
class Session:
    id: str
    messages: list[dict] = field(default_factory=list)
    results: dict[str, CitedResult] = field(default_factory=dict)
    busy: threading.Lock = field(default_factory=threading.Lock, repr=False)


class ClaudeAgent:
    name = "claude"

    def __init__(self, ctx: ToolContext, settings: AgentSettings | None = None, client: ModelClient | None = None):
        self.ctx = ctx
        self.settings = settings or load_settings()
        self.client = client or AnthropicClient(self.settings)
        self.sessions: dict[str, Session] = {}
        self._sessions_lock = threading.Lock()
        hub_ids = list(ctx.data.hubs)
        self.tools = tool_definitions(hub_ids)
        self.answer_schema = final_answer_schema(hub_ids)
        self.system = system_prompt(ctx)
        self.facts = prompt_facts(ctx)
        self.hub_names = {h: rec.city for h, rec in ctx.data.hubs.items()}

    def request(self, messages: list[dict]) -> dict[str, Any]:
        s = self.settings
        request = {
            "model": s.model,
            "max_tokens": s.max_tokens,
            "system": self.system,
            "tools": self.tools,
            "messages": messages,
            "output_config": {"effort": s.effort, "format": {"type": "json_schema", "schema": self.answer_schema}},
            "cache_control": {"type": "ephemeral"},
        }
        if s.fallbacks:
            request.update(betas=[s.fallback_beta], fallbacks=s.fallbacks)
        return request

    def answer(self, session_id: str | None, message: str) -> AgentReply:
        """Answer one message; session_id None starts a new conversation. A conversation this agent does not
        hold is refused without a model call, so a follow-up is never answered without its context (owner,
        milestone 4). A second message on a conversation that is still being answered is refused at once
        (owner, 2026-11-24): two turns at the same moment would corrupt the conversation."""
        with self._sessions_lock:
            if session_id:
                session = self.sessions.get(session_id)
                if session is None:
                    return self._refused(session_id, UNKNOWN, "unknown_conversation")
            else:
                session = Session(id=uuid.uuid4().hex)
                self.sessions[session.id] = session
        if not session.busy.acquire(blocking=False):
            return self._refused(session.id, BUSY, "busy")
        try:
            return self._answer(session, message)
        finally:
            session.busy.release()

    def _refused(self, session_id: str, text: str, code: str) -> AgentReply:
        return AgentReply(session_id=session_id, status="error", verdict="", error=text, error_code=code,
                          trace=Trace(model=self.settings.model))  # fmt: skip

    def _answer(self, session: Session, message: str) -> AgentReply:
        kept_messages, kept_results = len(session.messages), set(session.results)
        session.messages.append({"role": "user", "content": message})
        started = time.monotonic()
        deadline = started + self.settings.message_time_limit_seconds
        usage = dict.fromkeys(USAGE_FIELDS, 0)
        cost: float | None = 0.0
        calls: list[ToolCallRecord] = []
        model = self.settings.model
        repair_problems: list[str] = []
        rejected: str | None = None

        def trace() -> Trace:
            return Trace(model=model, tool_calls=calls, repaired=bool(repair_problems),
                         repair_problems=repair_problems, rejected_answer=rejected,
                         latency_ms=int(1000 * (time.monotonic() - started)),
                         usage={**usage, "cost_usd": None if cost is None else round(cost, 6)})  # fmt: skip

        def fail(text: str, code: str) -> AgentReply:
            del session.messages[kept_messages:]  # the failed turn leaves no trace in the conversation
            for result_id in [r for r in session.results if r not in kept_results]:
                del session.results[result_id]
            return AgentReply(session_id=session.id, status="error", verdict="", error=text, error_code=code,
                              trace=trace())  # fmt: skip

        for _ in range(self.settings.max_model_calls):
            try:
                response = self._call(self.request(session.messages), deadline)
            except _Stop as stop:
                return fail(stop.text, stop.code)
            except Exception as error:  # the SDK's typed errors; reported by class, never with request contents
                return fail(f"The model could not be reached ({type(error).__name__}).", "model_call_failed")
            model = getattr(response, "model", model)
            this = {key: getattr(response.usage, key, 0) or 0 for key in USAGE_FIELDS}
            for key in USAGE_FIELDS:
                usage[key] += this[key]
            priced = self.settings.cost(model, this)  # each response at its own model's price
            cost = None if cost is None or priced is None else cost + priced

            if response.stop_reason == "refusal":
                return fail("The model declined to answer this request.", "declined")
            if response.stop_reason == "max_tokens":
                return fail("The model's reply was cut off at its length limit.", "cut_off")
            session.messages.append({"role": "assistant", "content": _echo(response.content)})

            live = _after_fallback(response.content)
            uses = [b for b in live if b.type == "tool_use"]
            if uses:
                session.messages.append({"role": "user", "content": [self._run(session, b, calls) for b in uses]})
                continue

            text = "".join(b.text for b in live if b.type == "text")
            answer, problems = self._parse(text, session)
            if not problems:
                return render(session.id, answer, session.results, trace())
            if repair_problems:
                return fail("The answer failed validation twice: " + "; ".join(problems), "invalid_twice")
            repair_problems, rejected = problems, text
            session.messages.append({"role": "user", "content": REPAIR.format(problems="\n- ".join(problems))})
        return fail(f"No final answer within {self.settings.max_model_calls} model calls.", "too_many_calls")

    def _call(self, request: dict[str, Any], deadline: float) -> Any:
        """One model call. Each attempt waits at most the per-call timeout or the time left in the message,
        whichever is shorter. A failure the SDK would retry is retried `max_retries` times, after the wait
        the API asks for when it fits in the time left; a longer wait ends the message at once."""
        s = self.settings
        for attempt in range(s.max_retries + 1):
            left = deadline - time.monotonic()
            if left <= 0:
                raise _Stop(f"No answer within the {s.message_time_limit_seconds:g}-second limit for one question. "
                            "Try again in a moment.", "time_limit")  # fmt: skip
            try:
                return self.client.create(timeout=min(s.timeout_seconds, left), **request)
            except Exception as error:
                wait = _retry_wait(error)
                if wait is None or attempt == s.max_retries:
                    raise
                if wait >= deadline - time.monotonic():
                    raise _Stop(f"The model could not be reached in time: its API asked to wait {wait:g} seconds "
                                "before a retry, longer than this question has left. Try again shortly.",
                                "model_call_failed") from error  # fmt: skip
                time.sleep(wait)
        raise AssertionError("unreachable: the last attempt returns or raises")

    def _run(self, session: Session, block: Any, calls: list[ToolCallRecord]) -> dict:
        result_id = f"R{len(session.results) + 1}"
        args = block.input if isinstance(block.input, dict) else {}
        record = ToolCallRecord(id=result_id, name=block.name, input=args)
        try:
            result = run_tool(self.ctx, block.name, args)
        except Exception as error:  # a tool bug must not leave a tool call without its result
            result = failure(block.name, "tool_failed", f"The tool failed ({type(error).__name__}).")
        session.results[result_id] = CitedResult(result_id, record, result)
        calls.append(record)
        content = json.dumps({"result_id": result_id, **result.model_dump()})
        return {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": not result.ok}

    def _parse(self, text: str, session: Session) -> tuple[FinalAnswer | None, list[str]]:
        try:
            answer = FinalAnswer.model_validate_json(text)
        except ValidationError as error:
            return None, [f"the final answer is not a valid answer object: {error.errors()[0]['msg']}"]
        return answer, check_answer(answer, session.results, self.facts, self.hub_names)


def _retry_wait(error: Exception) -> float | None:
    """Seconds to wait before retrying a failed call, or None when it is not retried. The SDK's own rule
    (anthropic/_base_client.py, _should_retry and _calculate_retry_timeout): connection errors and timeouts,
    and HTTP 408, 409, 429 and 5xx unless the `x-should-retry` header says otherwise; the wait the API asks
    for in `retry-after-ms` or `retry-after` (seconds) is kept. A `retry-after` given as a date, which the
    SDK also reads, gets the first back-off instead."""
    import anthropic

    if isinstance(error, anthropic.APIConnectionError):  # includes APITimeoutError
        return FIRST_RETRY_PAUSE
    if not isinstance(error, anthropic.APIStatusError):
        return None
    headers = error.response.headers
    flag = headers.get("x-should-retry")
    if flag == "false" or (flag != "true" and error.status_code not in (408, 409, 429) and error.status_code < 500):
        return None
    for name, per_second in (("retry-after-ms", 1000), ("retry-after", 1)):
        try:
            seconds = float(headers.get(name)) / per_second
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            return seconds
    return FIRST_RETRY_PAUSE


def _last_fallback(content: list) -> int:
    return max((i for i, b in enumerate(content) if b.type == "fallback"), default=-1)


def _echo(content: list) -> list:
    """The assistant turn as it is sent back: unchanged, except the API's rule after a fallback."""
    boundary = _last_fallback(content)
    return [b for i, b in enumerate(content) if i >= boundary or b.type not in _BEFORE_FALLBACK_LEFT_OUT]


def _after_fallback(content: list) -> list:
    """The blocks the serving model produced: after the final fallback block, or all of them."""
    return content[_last_fallback(content) + 1 :]
