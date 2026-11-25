# Architecture

This is how the Weather Risk Intelligence Agent is built today, for an engineer reviewing the take-home. The grade is an interview take-home prototype: one process on one machine, no login, no production hardening (`docs/PLAN.md`, top). Where the plan said otherwise, `docs/PLAN.md` ("Deviations") and `docs/DECISIONS.md` record the change, and the code is the reference.

The system ranks twelve fictional hubs by weather exposure. Deterministic Python computes every figure from stored public data. A Claude model reads the question, calls our tools and writes a short verdict. Code validates the verdict, checks each number in it against the tool results, and builds every table itself.

## How one question flows

```
 Browser: one static page                      src/wra/api/static/index.html
   |  POST /api/chat {"session_id", "message"}
   v
 HTTP API (FastAPI)                            src/wra/api/app.py
   |  agent.answer(session_id, message)        HTTP status chosen from the reply
   v
 Agent loop  <--- Messages API --->  Claude    src/wra/agent/loop.py
   |  sends: system prompt, history, six strict tools, final-answer schema
   |  gets:  tool calls, then the final answer as JSON
   |  run_tool(name, arguments)
   v
 Six tools                                     src/wra/tools/
   v
 Scoring core, pure functions                  src/wra/scoring/
   v
 Plain values, read once                       src/wra/stored.py
   ^
 data/wra.sqlite  <-- wra ingest, offline      src/wra/ingest/build.py, store.py
                  <-- data/raw/, committed     checksummed responses
                  <-- wra ingest --refresh     src/wra/ingest/fetch.py: IEM, FEMA NRI, ACIS
```

Example: asked "Which hubs in the Midwest are most exposed to winter disruption?", Claude calls `rank_hubs` with hazard `winter` and region `midwest`. Code returns result `R1`: the figures, a ready-made table, and its sources, period and confidence. Claude's final answer cites `R1`. Code checks it, then sends the page the verdict with `R1`'s table and footnote.

## Components

**Ingest.** `wra ingest --refresh` (`src/wra/ingest/fetch.py`, the only module that uses the network) makes four requests per hub: the NOAA station service ACIS, for coordinates and daily snowfall and precipitation; FEMA's National Risk Index (NRI) at those coordinates; and the Iowa Environmental Mesonet (IEM) warning archive twice, for warnings issued for the county or forecast zone holding the point and for warnings whose drawn area covered it. Responses are kept under `data/raw/` with a manifest of URL, time and SHA-256 checksum. Plain `wra ingest` rebuilds the database from them offline (`src/wra/ingest/build.py`). It stops if a file changed after it was fetched, answers a different request than the code would send today, or names a place in another state. `src/wra/ingest/store.py` writes seven SQLite tables, keeping every warning row whether scored or not. `src/wra/stored.py` reads them once into plain values, so no tool runs SQL.

**Scoring.** The score is expected disruption days a year (EDD), summed over four hazards. Every rule is in `config/scoring.toml`.

- `src/wra/scoring/warning_time.py` turns warnings of the hazard's types into time, merging overlaps and assigning each hour to its year in the hub's time zone.
- `src/wra/scoring/kpi.py` divides by ten years, multiplies by the weight (1.0 for winter, flood and severe storms), and adds FEMA's hurricane frequency times 5.0 days per event. It ranks on figures rounded to two decimals, ties broken by hub id, and bands overall figures at 1, 2 and 3 days. A what-if re-weighs the stored counts without recounting.

**The six tools.** `run_tool` in `src/wra/tools/registry.py` is the one entry point. It validates arguments with Pydantic and returns a refusal as an error result instead of raising. The loop turns any other tool exception into a `tool_failed` result (`_run` in `src/wra/agent/loop.py`).

| Tool | Arguments | Returns |
|---|---|---|
| `list_hubs` | region | id, city, state, region, station, county |
| `rank_hubs` | hazard or overall, region, `top_n`, `weight_changes` | ranked rows, gap and ratio to the next, whether each is clear of the next; for overall, bands, breakdown, stability test |
| `compare_hubs` | 2 to 4 hub ids, hazards | each hub's difference and ratio to the group's most exposed |
| `explain_hub` | hub id | total, band, rank, neighbours; per hazard the rate, weight, share, quietest and worst year |
| `daily_weather_stats` | hub id, snowfall or precipitation, years (null means last full year), threshold | days observed, missing, meeting the threshold, trace days, percentage |
| `get_methodology` | none | weights, warning types, bands, period, sources, known limits |

## Repository structure

```
config/          hubs.toml (the 12 hubs), scoring.toml (weights, warning types, bands, confidence),
                 agent.toml (model, time and call limits, the public site's limits)
data/raw/        the public APIs' responses, committed: acis, fema_nri, iem_zone, iem_polygon
data/wra.sqlite  built from data/raw by `wra ingest`, no network; git-ignored
src/wra/
  cli.py         the `wra` command: ingest, data-report, rank, ask, chat, eval, serve
  ingest/        fetch (fetch.py, the only module that uses the network), parse, build the database
  scoring/       warning time, the KPI, confidence: pure functions, no model
  tools/         the six tools the model calls, one module each, and their registry
  agent/         the loop on the Claude API, the answer schema, the checks, the tables code writes
  api/           the HTTP API, the page (static/index.html), public mode (public.py)
  evals/         the 14 cases, the graders, the runner, the API check scripts/e2e.sh uses
tests/           on a scripted fake model: no network, no paid call
evals/runs/      the evaluation records the results document cites
scripts/e2e.sh   the end-to-end check from a fresh clone
Dockerfile       the public site's image
docs/            SUMMARY, ARCHITECTURE, EVAL_RESULTS, DECISIONS, ASSUMPTIONS, PLAN, DEPLOY_DESIGN,
                 DEPLOY_PLAN; ai-session/ holds the AI sessions
```

One Python package: the page is a single static file, so a separate front-end project would add a second toolchain for nothing.

## Data storage

**SQLite: one file, built offline from the committed raw responses.**

| Table | Holds | Rows today |
|---|---|---|
| `hubs` | each hub's station, coordinates, county and warning zones | 12 |
| `warning_events` | one row per warning: type, level, issue and expiry times, matched by zone or by drawn area | 17,619 |
| `station_daily` | one row per hub per day: snowfall, rain, trace and missing flags | 43,836 |
| `fema_nri` | FEMA's figures for each hub's county | 96 |
| `fetch_log` | what was fetched, from where, when, with a checksum | 48 |
| `skipped_records` | records the ingest set aside, and why | 750 |
| `meta` | the data period | 4 |

- **Why:** answers are fast and repeatable, the demo does not depend on the data providers' servers, and the evaluation's expected answers stay fixed. Raw warnings are stored and the time under warning is computed by tested code, so any figure can be traced to individual warnings.
- **Rejected:** calling the APIs for each question (slow, and answers would drift); Postgres (a running server for one reader of tens of thousands of rows); plain JSON files (every filter and count in ad-hoc Python).
- **Refreshing:** `wra ingest --refresh` fetches everything again (48 requests).

## Contracts between the model and the code

**Tool arguments.** `src/wra/agent/tooldefs.py` generates each tool's JSON schema from its Pydantic model and sends it with `strict: true`, which makes the API guarantee the arguments match. Strict mode supports only part of JSON Schema, so numeric bounds, length limits and patterns are dropped and enforced by Pydantic in `run_tool`. Hub fields become an enumeration of the twelve ids, so the model cannot name a city with no hub.

**Tool results.** Every tool returns one envelope (`src/wra/tools/envelope.py`): `ok`, `tool`, `data` (the figures the model may quote), `display` (the table, its `what_counts` line and fixed `notes`, all written by code), `provenance` (sources, period, data date, confidence label and reason, what-if flag) and, on failure, `error` with a code such as `no_data_for_period` or `unknown_hub`. The loop adds a `result_id` (`R1`, `R2`, ...), numbered across the conversation, which the answer cites. The API's own tool-use ids were rejected: the model cannot see them, and in the milestone 3 spike it invented one (`docs/DECISIONS.md`).

**The final answer.** The request asks for structured output matching the schema generated from `FinalAnswer` (`src/wra/agent/schemas.py`); Pydantic validates it again, extra fields forbidden.

| Field | Meaning |
|---|---|
| `status` | `answered`, `out_of_scope`, `no_data` or `needs_clarification` |
| `verdict` | the prompt asks for at most four short sentences; bold is the only formatting shown |
| `evidence` | result ids whose tables the page shows, in order |
| `hubs_ranked` | the order the verdict asserts, most exposed first |
| `hubs_from` | `top` or `bottom`: which end of the cited order those hubs are |
| `is_what_if` | true exactly when a cited result is a what-if |
| `hazard_orders` | for a comparison across several hazards, each hazard with its hubs, most exposed first; checked against the cited result, because one `hubs_ranked` holds one order and prose cannot be read reliably |
| `caveats` | zero to three short sentences |

The reply the API sends (`AgentReply`, same file) adds `session_id`, `tables`, `footnote`, `error`, `error_code` and a `trace` (tool calls, repair reasons, latency, tokens, cost). `src/wra/agent/render.py` fills `tables` and `footnote` from the cited results; the model never types either.

## The agent loop

`src/wra/agent/loop.py` is our own loop on the Anthropic Messages API. Each request carries the model and effort from `config/agent.toml` (today `claude-haiku-5-5`, effort `medium`, the owner's choice from the model comparison in `docs/EVAL_RESULTS.md`; `WRA_MODEL` and `WRA_EFFORT` override), the system prompt (`src/wra/agent/prompt.py`), tools, history, answer schema and a prompt-caching marker. The server-side refusal fallback is sent when `fallbacks` is set; it is off, because Haiku 5.5 has none. A message gets at most 6 model calls. A refused reply becomes a `declined` error; one cut off at 16,000 tokens becomes `cut_off`.

Conversations live in memory in the one agent object. A lock per conversation refuses a second message while the first is answered (`busy`). An unknown id, as after a restart, is refused without a model call (`unknown_conversation`). A turn ending in any error is removed whole, so the next question never sees a rejected answer.

One message has 90 seconds; each call waits at most 60 or the time left. The SDK's retries are off, and the loop retries once by the SDK's own rule for which failures to retry. If the API asks for a wait longer than the time left, the message ends at once (`_call`, `_retry_wait`).

## Validation, repair and the grounding check

After the schema check, `check_answer` (`src/wra/agent/checks.py`) requires:

1. every evidence id is a real result, and an `answered` reply cites one that succeeded;
2. `hubs_ranked` is the top of a cited order, or its bottom when `hubs_from` says so;
3. `is_what_if` matches the cited results, and each `hazard_orders` entry is the start of that hazard's cited order;
4. grounding, below;
5. in each sentence, the first band named after a hub is that hub's cited band;
6. no Markdown table in the verdict, at most three caveats.

On any failure the problems go back to Claude once; it may call tools, then answers again. A second failure ends the message as `invalid_twice`. Nothing unverified reaches the page.

Grounding (`src/wra/agent/grounding.py`): every number written in digits in the verdict and caveats must equal, after rounding half up to the decimals written, a number in the cited results, their arguments, or the figures the system prompt states (period years, FEMA's record years, hub count). It does not read number words, so "roughly twice" goes unchecked. It checks that a figure is in a cited result, not which hub or hazard it belongs to, so a right figure for the wrong hub passes. A small whole number nearly always matches something, such as a rank, so a wrong "3" can pass (`docs/ASSUMPTIONS.md`, milestone 2 section, point 12, and milestone 5 section). The tables beside the verdict always show the true figures.

## How confidence is computed

Every result carries a label (high, medium, low) and a one-line reason from `src/wra/scoring/confidence.py`, built on three tests:

- **Coverage:** the share of the records a figure needs that the data holds.
- **Separation:** a gap between two hubs passes when it exceeds the combined standard error of their ten yearly figures. Hurricanes have no yearly series, so their gaps are "not testable".
- **Stability,** overall rankings only: each of the four weights halved and doubled. Do the top hub and the top-three set hold?

**Low:** coverage below 90%, more than half the tested gaps failing, or a new top hub in a variant. **High:** coverage of at least 98%, no failed or untestable gap, and a stable top three. **Medium:** anything else, so a hurricane gap caps a result at medium. Daily station figures use the missing share: high up to 2% of days, medium up to 10%. A footnote over several results takes the lowest label; when several results give it, each reason is led by its table's name, and a period they share is shown once (`src/wra/agent/render.py`). Today's overall ranking is low: 10 of its 11 neighbour gaps fail separation (`uv run wra rank overall`).

## The API and the chat page

`src/wra/api/app.py` serves `POST /api/chat` (`{"session_id": null or an id, "message": "..."}`), `GET /api/hubs` and `GET /healthz` (no model call), the page at `GET /`, and FastAPI's reference at `/docs`. Table cells go out as text (2.9 as 2.90), so the page formats no figure. `wra serve` listens on 127.0.0.1, port 8000, so only this machine can spend the API credit.

On any other address it runs in public mode (`src/wra/api/public.py`, design in `docs/DEPLOY_DESIGN.md`). The mode follows the listen address, not a flag, so it cannot be forgotten. Without `WRA_ACCESS_CODE` the server refuses to start; with it, every route but `/healthz` needs HTTP Basic sign-in (username `analyst`, the code as password, both compared as UTF-8 bytes in constant time), and the agent gets a daily limit (`src/wra/agent/limits.py`, 100 questions a UTC day), which it checks after the busy and unknown-conversation refusals and before any model call. The agent holds at most 200 conversations in either mode and drops the least recently used. The public site runs on Render (a paid 512 MB instance that does not sleep) from the image the `Dockerfile` builds, with the database built inside it.

The page (`src/wra/api/static/index.html`) is one file with inline script and styles, using plain `fetch`; a test checks it loads nothing from outside (`tests/test_api.py`). It escapes all reply text, then turns `**...**` into bold. It shows the verdict, caveats, tables, the data and confidence lines, and a "How this was computed" panel from the trace.

## How failures surface

Every agent reply has the same body. The status comes from `error_code`, never from the message text.

| HTTP status | When | `error_code` |
|---|---|---|
| 200 | any reply that is not an error | none |
| 409 | the last question is still being answered | `busy` |
| 404 | the server does not hold this conversation | `unknown_conversation` |
| 502 | the model side failed | `model_call_failed`, `time_limit`, `declined`, `cut_off`, `invalid_twice`, `too_many_calls` |
| 500 | a bug in our own code; the turn is removed | `internal_error` |
| 429 | public mode: the day's question limit is used up; no model call | `daily_limit` |
| 422 | a malformed request: FastAPI's message, not a reply; no model call | none |
| 401 | public mode: no sign-in, or a wrong one; a short message, not a reply; no model call | none |

## The evaluation

`src/wra/evals/` holds fourteen cases, five graders and the runner, started by `uv run wra eval`. The cases are the four assignment questions, two follow-ups, a what-if and the return from it, an overall top three, the method, three out-of-scope questions and a year outside the data.

- The runner calls the same `answer()` the API calls, with the clock pinned to 2026-11-24.
- The checks are code, never a model: `status`, `tool`, `hubs`, `numbers`, `mentions`. Expected orders, names and bands come from the scoring code at grading time. One hand-checked figure is pinned: Denver International, 2025, 26 days of measurable snowfall of 364 observed.
- The report gives the score, errors by kind, repairs by cause, time, tokens and cost at list price. Runs are saved under `evals/runs/`, which git ignores unless a results document cites the run.
- `--agent stub` runs everything with an agent that answers nothing, at no cost.

The target: the four assignment questions pass in all three repetitions, and at least 90% of all case runs pass (`docs/PLAN.md`, section 10.3). The report's last line says whether it was met (`target_met` in `src/wra/evals/run.py`), and `--require-target` makes a miss fail the command. `uv run pytest -q` never calls the API; the loop and the API run against a scripted fake model (`tests/test_agent_loop.py`).

## Final end-to-end check

`scripts/e2e.sh` checks the last commit, not the working copy. It clones the repository into a temporary folder and points the clone at the original's `.env` through the `WRA_ENV_FILE` setting (`src/wra/paths.py`), so the key is never copied or printed. It runs `uv sync`, `uv run wra ingest` from the committed raw responses, and `uv run pytest -q` inside the clone. Those steps cost nothing and run by default.

With `--paid` it goes on to spend API credit. It starts `wra serve` on port 8765, with the date pinned to 2026-11-24 as in the evaluation, and, through the HTTP API only, asks the four assignment questions, one follow-up and one out-of-scope question (`src/wra/evals/e2e.py`). Each reply must parse as an `AgentReply` with the expected status, and the follow-up ("And which is the least exposed?" after the Midwest winter question) must name the last hub of the Midwest winter ranking, worked out from the scoring code, and show that ranking's table: Columbus is last in the Midwest overall ranking too. Without `--paid` the script's last line says only its free part passed. Last, it runs `uv run wra eval --reps 3 --require-target`, which fails the script when the target is missed, and copies the run record back into `evals/runs/`.

## Left out on purpose

- **No agent framework or Managed Agents.** Validation and repair must sit inside a loop we control; Managed Agents is in beta and bills session time (`docs/DECISIONS.md`).
- **No forced "answer" tool.** On Opus 5.5 and Sonnet 5.5 a tool call cannot be forced, so structured output shapes the answer (`docs/PLAN.md`, section 9).
- **No live calls from tools.** A public server could be down during a demo, and an evaluation over moving data has no fixed answers.
- **No JavaScript packages or build step.** One static page with `fetch` meets the brief.
- **No Markdown library.** In two evaluation runs the model wrote only bold (`docs/ASSUMPTIONS.md`, milestone 4 section, point 4).
- **No streaming.** The answer must pass validation before anything is shown.
- **No stored conversations, logins or second process.** A conversation ends with the server.

Runtime dependencies: `anthropic`, `fastapi`, `uvicorn`, `httpx`, `pydantic`, `python-dotenv`; `pytest` for development (`pyproject.toml`).
