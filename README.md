# Weather Risk Intelligence Agent

An agent that helps a logistics company's analysts decide which distribution hubs are most exposed to weather disruption.

- **Try it:** https://weather-risk-agent-7iai.onrender.com/ (sign in as `analyst` with the access code sent with the submission; it comes down after the interview), or run it locally (below).
- **How it works:** twelve hubs, three public data sources, one measure (expected disruption days a year), all computed in plain Python. A Claude model (Haiku 5.5) reads the question, calls six tools and explains the result. Code checks every answer against a schema and every figure in it against the tool results.
- **Does it work:** fourteen test questions, asked three times each, passed 42 of 42 in the final end-to-end check from a fresh clone (commit `27c5b6d`).

**Read in this order:**

1. [docs/SUMMARY.md](docs/SUMMARY.md): one page, for the analysts' manager.
2. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the components and how they talk, the repository structure, the data storage choice.
3. [docs/EVAL_RESULTS.md](docs/EVAL_RESULTS.md): the evaluation, the model choice, the four example answers and the limits.

The record behind them: [docs/DECISIONS.md](docs/DECISIONS.md) (why each choice was made), [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) (what the data showed and what is assumed), [docs/PLAN.md](docs/PLAN.md) (the approved plan and how the build departed from it), [docs/DEPLOY_DESIGN.md](docs/DEPLOY_DESIGN.md) (the public site) and [docs/ai-session/](docs/ai-session/) (the full AI sessions).

## Run it

Needs [uv](https://docs.astral.sh/uv/). Run from the repository root.

```
uv sync
uv run wra ingest          # builds data/wra.sqlite from the stored responses, no network, about a second
uv run wra data-report     # prints what the database holds, hub by hub
uv run wra rank overall    # the ranking of all twelve hubs, with bands and confidence
uv run wra rank winter --region midwest
uv run wra eval --agent stub   # runs the fourteen evaluation cases; a stub agent scores 0 of 14
uv run pytest -q
scripts/e2e.sh             # the end-to-end check, free part: clones the last commit, builds offline, runs the tests there
```

The agent needs an Anthropic API key. Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY`; `.env` is git-ignored. `WRA_ENV_FILE` names another file instead; the end-to-end script's clone uses it to read the original repository's `.env` without copying it. These commands make paid API calls:

```
uv run wra serve           # the chat page at http://127.0.0.1:8000/ and its API; every question is paid
uv run wra ask "Which hubs in the Midwest are most exposed to winter disruption?"
uv run wra chat            # a conversation in the terminal, follow-ups included
uv run wra eval            # all fourteen cases through the real agent; 0.014 USD a repetition on Haiku (2026-11-24)
scripts/e2e.sh --paid      # the whole end-to-end check: six questions through the API, then wra eval --reps 3
```

The model and its effort level are in `config/agent.toml`; `WRA_MODEL` and `WRA_EFFORT` override them. One question gets about 90 seconds, all model calls included, before it ends in a plain error.

`wra eval` ends with a line saying whether the plan's target was met: the four assignment questions pass in every repetition, and at least 90% of all case runs pass. `--require-target` makes the command fail when it was not. `scripts/e2e.sh --paid` starts the server on port 8765 (`WRA_E2E_PORT` changes it) with the date pinned to 2026-11-24, as the evaluation pins it, asks the four assignment questions, a follow-up and an out-of-scope question through the HTTP API, checks each reply, then runs `wra eval --reps 3 --require-target` and copies its record into `evals/runs/`.

`wra serve` listens on this machine only (127.0.0.1, port 8000); `--host` and `--port` change that. The page sends `POST /api/chat` with `{"session_id": null, "message": "..."}` and gets back the validated reply; sending that reply's `session_id` with the next message makes it a follow-up. Every reply has the same shape. Its HTTP status is 200 unless it is an error: 409 while the conversation's last question is still being answered, 404 for a conversation the server no longer holds (after a restart), 502 when the model could not give a validated answer, 500 for a bug in the agent's own code. A malformed request gets 422 with FastAPI's validation message instead of a reply. `GET /api/hubs` lists the hubs and `GET /healthz` checks the server; neither calls the model. FastAPI's generated reference for the API is at `/docs`.

`wra rank` takes `overall`, `winter`, `flood`, `severe_storm` or `hurricane`, an optional `--region` (`midwest`, `south`, `west`) and `--top N`. None of these commands uses the network. The scoring rules (weights, warning types, bands, confidence thresholds) are in `config/scoring.toml`.

`uv run wra ingest --refresh` fetches everything again from the public services first (48 requests, about 90 seconds). It is not needed to run the project: the responses fetched on 2026-11-24 are stored under `data/raw/`.

### Public mode

`wra serve` on any address but 127.0.0.1, localhost or ::1 runs in public mode, which is how the public site is built to run. It needs an access code in `WRA_ACCESS_CODE` and refuses to start without one (exit status 2). Every route but `/healthz` then asks for sign-in in the browser's own box: the username `analyst` and the access code as the password. At most 100 questions a day (UTC) reach the model; past that a question gets a plain message, HTTP 429 and no model call. In either mode the server holds at most 200 conversations and drops the one used least recently. Both limits are in `config/agent.toml`. The daily count is kept in memory and starts again whenever the server restarts, so run the public site with a key from a separate Anthropic workspace that has its own monthly spending limit: that limit is the ceiling on spend.

The public site runs on Render from the image the `Dockerfile` builds: the database is built inside it, and `.dockerignore` keeps `.env` out. The design is in [docs/DEPLOY_DESIGN.md](docs/DEPLOY_DESIGN.md).
### Checking the page by hand before a demo

Three things the page does have no automated test: the question put back in the box after a failure, the reset when the server no longer holds the conversation, and "New conversation". This check covers them in about three minutes, with one paid question.

1. Start `uv run wra serve` and open http://127.0.0.1:8000/. Ask "Which hubs are most exposed overall?". While "Working" shows, Ask and New conversation are greyed out. The answer appears with its table, its data and confidence lines, and a "How this was computed" panel.
2. Stop the server (Ctrl+C) and start it again; leave the page open. Send "And which is the least exposed?". The page shows "New conversation. Your question is back in the box: send it again, reworded if it was a follow-up." and the question is back in the box. No model call is made.
3. Click New conversation. The answers clear; the text in the box stays.
4. Stop the server. Send any question. The page shows "The server could not be reached. The question is back in the box." and the question is back in the box.

### Interview day

- **The day before:** run `scripts/e2e.sh` (free: a fresh clone, the database built offline, the tests), so the laptop backup is proven. Open the public URL, sign in and ask one question (paid, under a cent on Haiku).
- **Fifteen minutes before:** open the public URL, sign in and ask one question, so any fault shows before the call.
- **If the public URL fails:** `uv run wra serve`, open http://127.0.0.1:8000/ and share the screen.
- Keep the access code at hand, outside the repository.

## How the build sessions were run

The full Claude Code sessions are in [docs/ai-session/](docs/ai-session/). Two tools from the owner's Claude Code setup carried context from one session to the next. Neither is part of this repository.

- **`handoff` skill (the owner's own):** closes a session. A fresh reviewer checks the session's changes, the work queue in `.claude/QUEUE.md` is re-sorted, and Claude writes a prompt for the next session. From session 02 on, the prompt is also saved in the `remember` plugin's handoff file, so the next session is shown it when it starts. The owner still opens that session with a short message, because the plugin presents the saved prompt as information, not as an instruction to act on.
- **`remember` plugin (by Digital Process Tools, installed from the `claude-plugins-official` marketplace):** keeps running notes of each session in a local `.remember/` folder, which git ignores, and loads them into the next session when it starts.

## Data sources

- Iowa Environmental Mesonet warning archive: past National Weather Service warnings for each hub's location.
- FEMA National Risk Index: yearly hurricane frequency for each hub's county, and FEMA's frequencies for the other hazards as a cross-check. Endpoint: `https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0` (FEMA's National Risk Index Counties map service), dataset version "December 2025", retrieved 2026-11-24 (10:42 UTC, as the fetch log records).
- NOAA airport weather stations, through the ACIS web service: measured daily snowfall and rainfall.

This product uses the Federal Emergency Management Agency's National Risk Index dataset API or downloadable datasets but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s).
