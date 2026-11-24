"""The agent loop on the Anthropic Messages API (plan sections 7 and 8).

One user message: call Claude with the system prompt, the conversation, six strict tools and the
final-answer schema; run the tools it calls and send the results back; when it answers, validate the
answer in code. One repair attempt if anything fails, then a clear error. At most `max_model_calls`
model calls per message. A refused or cut-off reply becomes an error. Nothing unverified is shown.

Every response is appended to the conversation unchanged, thinking blocks included, which is what
Opus 5.5 requires. Each tool result is stamped with a short result id (R1, R2, ...) that the final
answer cites as evidence; the milestone 3 spike showed the model invents ids it cannot see.
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import ValidationError

from wra.agent.checks import CitedResult, check_answer
from wra.agent.prompt import system_prompt
from wra.agent.render import render
from wra.agent.schemas import AgentReply, FinalAnswer, ToolCallRecord, Trace
from wra.agent.settings import AgentSettings, load_settings
from wra.agent.tooldefs import final_answer_schema, tool_definitions
from wra.tools.context import ToolContext
from wra.tools.registry import run_tool

REPAIR = (
    "Your final answer failed these checks:\n- {problems}\nAnswer again with a corrected final answer object. "
    "You may call tools first if you need a result to cite."
)
USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


class ModelClient(Protocol):
    def create(self, **request: Any) -> Any: ...


class AnthropicClient:
    """The real client. The key comes from the environment, which `.env` fills via python-dotenv."""

    def __init__(self) -> None:
        import anthropic
        from dotenv import load_dotenv

        from wra import paths

        load_dotenv(paths.root() / ".env")
        self._client = anthropic.Anthropic()

    def create(self, **request: Any) -> Any:
        return self._client.beta.messages.create(**request)


@dataclass
class Session:
    id: str
    messages: list[dict] = field(default_factory=list)
    results: dict[str, CitedResult] = field(default_factory=dict)


class ClaudeAgent:
    name = "claude"

    def __init__(self, ctx: ToolContext, settings: AgentSettings | None = None, client: ModelClient | None = None):
        self.ctx = ctx
        self.settings = settings or load_settings()
        self.client = client or AnthropicClient()
        self.sessions: dict[str, Session] = {}
        hub_ids = list(ctx.data.hubs)
        self.tools = tool_definitions(hub_ids)
        self.answer_schema = final_answer_schema(hub_ids)
        self.system = system_prompt(ctx)

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
        session = self.sessions.get(session_id) if session_id else None
        if session is None:
            session = Session(id=session_id or uuid.uuid4().hex)
            self.sessions[session.id] = session
        session.messages.append({"role": "user", "content": message})
        started = time.monotonic()
        usage = dict.fromkeys(USAGE_FIELDS, 0)
        calls: list[ToolCallRecord] = []
        model = self.settings.model
        repaired = False
        repair_problems: list[str] = []

        def trace() -> Trace:
            cost = self.settings.cost(model, usage)
            return Trace(model=model, tool_calls=calls, repaired=repaired, repair_problems=repair_problems,
                         latency_ms=int(1000 * (time.monotonic() - started)),
                         usage={**usage, "cost_usd": None if cost is None else round(cost, 6)})  # fmt: skip

        def fail(text: str) -> AgentReply:
            return AgentReply(session_id=session.id, status="error", verdict="", error=text, trace=trace())

        for _ in range(self.settings.max_model_calls):
            try:
                response = self.client.create(**self.request(session.messages))
            except Exception as error:  # the SDK's typed errors; reported by class, never with request contents
                return fail(f"The model could not be reached ({type(error).__name__}).")
            model = getattr(response, "model", model)
            for key in USAGE_FIELDS:
                usage[key] += getattr(response.usage, key, 0) or 0

            if response.stop_reason == "refusal":
                return fail("The model declined to answer this request.")
            if response.stop_reason == "max_tokens":
                return fail("The model's reply was cut off at its length limit.")
            session.messages.append({"role": "assistant", "content": response.content})

            uses = [b for b in response.content if b.type == "tool_use"]
            if uses:
                session.messages.append({"role": "user", "content": [self._run(session, b, calls) for b in uses]})
                continue

            text = "".join(b.text for b in response.content if b.type == "text")
            answer, problems = self._parse(text, session)
            if not problems:
                return render(session.id, answer, session.results, trace())
            if repaired:
                return fail("The answer failed validation twice: " + "; ".join(problems))
            repaired = True
            repair_problems = problems
            session.messages.append({"role": "user", "content": REPAIR.format(problems="\n- ".join(problems))})
        return fail(f"No final answer within {self.settings.max_model_calls} model calls.")

    def _run(self, session: Session, block: Any, calls: list[ToolCallRecord]) -> dict:
        result_id = f"R{len(session.results) + 1}"
        args = block.input if isinstance(block.input, dict) else {}
        record = ToolCallRecord(id=result_id, name=block.name, input=args)
        result = run_tool(self.ctx, block.name, args)
        session.results[result_id] = CitedResult(result_id, record, result)
        calls.append(record)
        content = json.dumps({"result_id": result_id, **result.model_dump()})
        return {"type": "tool_result", "tool_use_id": block.id, "content": content, "is_error": not result.ok}

    def _parse(self, text: str, session: Session) -> tuple[FinalAnswer | None, list[str]]:
        try:
            answer = FinalAnswer.model_validate_json(text)
        except ValidationError as error:
            return None, [f"the final answer is not a valid answer object: {error.errors()[0]['msg']}"]
        return answer, check_answer(answer, session.results)
