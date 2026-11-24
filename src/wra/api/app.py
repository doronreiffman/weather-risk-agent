"""The HTTP API and the chat page it serves (plan sections 7.1 and 8.5).

POST /api/chat answers one message through the agent. GET /api/hubs lists the hubs and GET /healthz says the
server is up, neither calling the model. GET / is the page. One agent per process holds every conversation
in memory. The endpoints are plain functions, so FastAPI runs each request in its thread pool; the agent's
lock per conversation keeps two messages on one conversation apart.

HTTP status (owner, milestone 4): every reply the agent gives is sent with the same body, as 200 unless it
is an error; busy is 409, a conversation the server does not hold is 404, and every other failure is on the
model's side, 502. A malformed request is FastAPI's 422 and reaches no model.
"""

from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, StringConstraints

from wra.agent.schemas import Agent, AgentReply
from wra.tools.context import ToolContext
from wra.tools.envelope import SOURCE_NAMES
from wra.tools.registry import run_tool
from wra.tools.text import cell_text

PAGE = Path(__file__).parent / "static" / "index.html"
MAX_MESSAGE = 2000  # characters; a question to this agent runs to a few hundred
ERROR_STATUS = {"busy": 409, "unknown_conversation": 404}  # any other error code: 502


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str | None = None  # null starts a new conversation
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE)]


def http_status(reply: AgentReply) -> int:
    return 200 if reply.status != "error" else ERROR_STATUS.get(reply.error_code or "", 502)


def for_page(reply: AgentReply) -> dict[str, Any]:
    """The reply as the page shows it: table cells as text by the command line's rule (2.9 as 2.90) and
    sources by name. The page then writes every figure exactly as given and formats none."""
    body = reply.model_dump(mode="json")
    body["tables"] = [{**t.model_dump(mode="json"), "rows": [[cell_text(c) for c in row] for row in t.rows]}
                      for t in reply.tables]  # fmt: skip
    if reply.footnote is not None:
        body["footnote"]["sources"] = [SOURCE_NAMES.get(s, s) for s in reply.footnote.sources]
    return body


def create_app(agent: Agent, ctx: ToolContext) -> FastAPI:
    app = FastAPI(title="Weather Risk Intelligence Agent")
    errors = {code: {"model": AgentReply, "description": text} for code, text in [
        (404, "The conversation is no longer on the server; nothing was sent to the model."),
        (409, "The conversation's last question is still being answered."),
        (502, "The model could not give a validated answer: unreachable, too slow, declined, or invalid twice."),
    ]}  # fmt: skip

    @app.post("/api/chat", response_model=AgentReply, responses=errors)
    def chat(request: ChatRequest) -> JSONResponse:
        reply = agent.answer(request.session_id, request.message)
        return JSONResponse(for_page(reply), status_code=http_status(reply))

    @app.get("/api/hubs")
    def hubs() -> dict[str, Any]:
        return {"hubs": run_tool(ctx, "list_hubs", {"region": "all"}).data["hubs"]}

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "hubs": len(ctx.data.hubs)}

    @app.get("/", include_in_schema=False)
    def page() -> FileResponse:
        return FileResponse(PAGE, media_type="text/html")

    return app
