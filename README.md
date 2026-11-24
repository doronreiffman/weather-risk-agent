# Weather Risk Intelligence Agent

An agent that helps a logistics company's analysts decide which distribution hubs are most exposed to weather disruption.

**Status: the data is in place (milestone 1 of 5).** Twelve hubs are loaded from three public sources into a local database. The risk score, the agent, the API and the chat page are not built yet. The design is in [docs/PLAN.md](docs/PLAN.md); what the data showed is in [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md).

## Run it

Needs [uv](https://docs.astral.sh/uv/). Run from the repository root.

```
uv sync
uv run wra ingest          # builds data/wra.sqlite from the stored responses, no network, about a second
uv run wra data-report     # prints what the database holds, hub by hub
uv run pytest -q
```

`uv run wra ingest --refresh` fetches everything again from the public services first (48 requests, about 90 seconds). It is not needed to run the project: the responses fetched on 2026-11-24 are stored under `data/raw/`.

## How the build sessions were run

The full Claude Code sessions are in [docs/ai-session/](docs/ai-session/). Two of the owner's own tools carried context from one session to the next. Neither is part of this repository.

- **`handoff` skill:** closes a session. A fresh reviewer checks the session's changes, the work queue in `.claude/QUEUE.md` is re-sorted, and Claude writes a ready-to-paste prompt for the next session.
- **`remember` plugin:** keeps running notes of each session in a local `.remember/` folder, which git ignores, and loads them into the next session when it starts.

## Data sources

- Iowa Environmental Mesonet warning archive: past National Weather Service warnings for each hub's location.
- FEMA National Risk Index: yearly hurricane frequency for each hub's county.
- NOAA airport weather stations, through the ACIS web service: measured daily snowfall and rainfall.

This product uses the Federal Emergency Management Agency's National Risk Index dataset API or downloadable datasets but is not endorsed by FEMA.
