# Weather Risk Intelligence Agent

An agent that helps a logistics company's analysts decide which distribution hubs are most exposed to weather disruption.

**Status: the chat page and its API are built (milestone 4 of 5); their live check with real questions is pending.** Twelve hubs are loaded from three public sources into a local database and ranked by expected disruption days a year, with code-computed confidence. An agent on Claude Opus 5.5 answers questions by calling six tools; code validates every answer, checks each number against the tool results and builds the tables. The first evaluation run passed 12 of 14 cases; two checks that failed right answers were corrected, a review tightened the answer checks, and the run on commit `097adfb` passed 14 of 14 with no repairs (see [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md)). Later commits changed the prompt and the client settings; no paid run has been made on them yet. The API and the page are tested on a scripted stand-in for the model, which makes no paid call. The design is in [docs/PLAN.md](docs/PLAN.md); what the data showed and what was decided along the way are in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md) and [docs/DECISIONS.md](docs/DECISIONS.md).

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
```

The agent needs an Anthropic API key. Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY`; `.env` is git-ignored. These commands make paid API calls:

```
uv run wra serve           # the chat page at http://127.0.0.1:8000/ and its API; every question is paid
uv run wra ask "Which hubs in the Midwest are most exposed to winter disruption?"
uv run wra chat            # a conversation in the terminal, follow-ups included
uv run wra eval            # all fourteen cases through the real agent; 0.53 USD at list price on 2026-11-24
```

The model and its effort level are in `config/agent.toml`; `WRA_MODEL` and `WRA_EFFORT` override them. One question gets about 90 seconds, all model calls included, before it ends in a plain error.

`wra serve` listens on this machine only (127.0.0.1, port 8000); `--host` and `--port` change that. The page sends `POST /api/chat` with `{"session_id": null, "message": "..."}` and gets back the validated reply; sending that reply's `session_id` with the next message makes it a follow-up. Every reply has the same shape. Its HTTP status is 200 unless it is an error: 409 while the conversation's last question is still being answered, 404 for a conversation the server no longer holds (after a restart), 502 when the model could not give a validated answer, 500 for a bug in the agent's own code. A malformed request gets 422 with FastAPI's validation message instead of a reply. `GET /api/hubs` lists the hubs and `GET /healthz` checks the server; neither calls the model. FastAPI's generated reference for the API is at `/docs`.

`wra rank` takes `overall`, `winter`, `flood`, `severe_storm` or `hurricane`, an optional `--region` (`midwest`, `south`, `west`) and `--top N`. None of these commands uses the network. The scoring rules (weights, warning types, bands, confidence thresholds) are in `config/scoring.toml`.

`uv run wra ingest --refresh` fetches everything again from the public services first (48 requests, about 90 seconds). It is not needed to run the project: the responses fetched on 2026-11-24 are stored under `data/raw/`.

## How the build sessions were run

The full Claude Code sessions are in [docs/ai-session/](docs/ai-session/). Two tools from the owner's Claude Code setup carried context from one session to the next. Neither is part of this repository.

- **`handoff` skill (the owner's own):** closes a session. A fresh reviewer checks the session's changes, the work queue in `.claude/QUEUE.md` is re-sorted, and Claude writes a prompt for the next session. From session 02 on, the prompt is also saved in the `remember` plugin's handoff file, so the next session is shown it when it starts. The owner still opens that session with a short message, because the plugin presents the saved prompt as information, not as an instruction to act on.
- **`remember` plugin (by Digital Process Tools, installed from the `claude-plugins-official` marketplace):** keeps running notes of each session in a local `.remember/` folder, which git ignores, and loads them into the next session when it starts.

## Data sources

- Iowa Environmental Mesonet warning archive: past National Weather Service warnings for each hub's location.
- FEMA National Risk Index: yearly hurricane frequency for each hub's county, and FEMA's frequencies for the other hazards as a cross-check. Endpoint: `https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0` (FEMA's National Risk Index Counties map service), dataset version "December 2025", retrieved 2026-11-24 (10:42 UTC, as the fetch log records).
- NOAA airport weather stations, through the ACIS web service: measured daily snowfall and rainfall.

This product uses the Federal Emergency Management Agency's National Risk Index dataset API or downloadable datasets but is not endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved from the Agency's website(s).
