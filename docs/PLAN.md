# Weather Risk Intelligence Agent: plan

Status: **approved by the owner on 2026-11-24.** Section 5 was revised the same day, before any scoring code existed: the score counts time under warning instead of calendar days touched, and the warning weights are neutral. The first entry under Deviations says why. Written 2026-11-24.

Grade assumed: **interview take-home prototype.** A clear, tested core that runs live on one machine. Single process, no login, no multi-user scaling, no production hardening. Anything beyond that is listed as out of scope or as a bonus.

This document is self-contained. Someone who has not seen the planning conversation should be able to build from it.

---

## 1. The problem, in the analysts' terms

A logistics company runs regional distribution hubs across the US. Severe weather closes hubs and delays shipments. Each year the company picks a handful of hubs for resilience upgrades. The analysts need to say **which hubs are most exposed to weather disruption**, in a form they can defend:

- a ranking that comes from a rule they can read, not from a model's opinion;
- an explanation short enough to repeat to their boss;
- a plain statement of what the data cannot tell them.

The agent answers questions such as these four from the assignment:

1. Which hubs in the Midwest are most exposed to winter disruption?
2. Compare Miami and Houston in terms of hurricane and flood exposure.
3. What percentage of days in Denver last year had snowfall?
4. Why is the Dallas hub's weather disruption risk high?

## 2. Decisions from the interview

The owner stood in for the analysts and answered eleven questions on 2026-11-24.

| # | Question | Decision |
|---|---|---|
| 1 | Does "exposure" include how important a hub is to the business? | No. Weather at the location only. We have no real business figures for a fictional company, so nothing in the score is invented. |
| 2 | Which hazards? | Four: winter weather, flooding, severe storms (tornado, hail, damaging wind), hurricanes. Heat is out. |
| 3 | How do different hazards combine into one score? | Weighted by how long each typically shuts a hub. Starting weights are recorded assumptions in a config file. |
| 4 | How much history? | The last 10 full years, 2016 to 2025. Hurricanes use FEMA's much longer record. |
| 5 | What counts as a disrupted day? | A day on which the National Weather Service had a warning in force for the hub's location. |
| 6 | "High" compared with what? | Fixed bands in disruption days per year. Not relative to our other hubs, not FEMA's rating. |
| 7 | Which record answers "what share of days had snowfall"? | Measured observations at the airport weather station, not a weather model's estimate. |
| 8 | Weather happening now, or forecasts? | Out of scope. The agent says so and explains why. |
| 9 | How far beyond ranking should the agent go? | Rank and explain only. Asked where to invest, it gives the ranking and names what the decision still needs. |
| 10 | Can analysts try different weights in the chat? | Yes, as a labelled what-if. The official weights do not change. |
| 11 | What does a good answer look like? | A two or three sentence verdict, a small table of the figures behind it, then fixed lines for data, period and confidence. |

Answers 3 and 5 were refined later the same day, with the owner's agreement: the score counts the time a warning was in force, not the calendar days it touched, and the three warning weights are equal. See Deviations.

## 3. Scope

**In scope**

- About a dozen fictional hubs (section 6), four hazards, one deterministic score.
- Six kinds of question: rank hubs, compare hubs, explain one hub's score, daily snowfall or rainfall statistics for a hub, what-if on weights, how the method works.
- Follow-up questions within a conversation.
- A chat page that talks to the agent through an HTTP API.
- An evaluation set with automatic checks and one command to run it.

**Out of scope, with reasons**

| Out | Why |
|---|---|
| Hub importance, upgrade costs, investment advice | No real business data exists. Inventing it would make the ranking indefensible. The agent states this limit when asked. |
| Live weather and forecasts | The decision is yearly. The Weather Service's live feed keeps only 7 days, so it cannot feed a long-run ranking. |
| Site-level flood risk (floodplain of the exact parcel) | Hubs are fictional and have no real addresses. This is the first thing a real engagement would add. |
| Heat, wildfire, earthquake, cold snaps | The owner chose four hazards. Heat and cold slow work more often than they close a hub. |
| Climate-change projections | The score describes the recent past. It does not forecast. |
| Cities with no hub | The agent says it has no hub there and lists the hubs it knows. |
| Logins, multiple users, scaling | Prototype grade. |

A narrow scope done well beats a broad one done shallowly, so every item above is refused by the agent in plain words instead of being answered badly.

## 4. Data sources

### 4.1 What was checked on 2026-11-24

Each source was tested with live requests by a subagent, and I re-ran one request per source myself before using its findings. Appendix A lists commands that reproduce the key results.

| Source | Result | Evidence |
|---|---|---|
| Open-Meteo historical weather API | Reachable. A full year of daily data with no missing values (the checker also fetched ten years in one call; I did not repeat that). Snowfall is a weather model's estimate, and the count of snow days depends heavily on the cut-off. Its terms say: "You may only use the free API services for non-commercial purposes." | Denver 2025: 43 days with any snowfall, 33 at 0.25 cm or more, 10 at 2.54 cm or more, 1 at 5 cm or more. |
| National Weather Service API, alerts | Reachable. Holds only the last 7 days. Its documentation says: "The /alerts endpoint contains alerts issued over the past seven days." | Asking for Texas alerts since 2025-01-01 returned 165 alerts, the oldest sent 2026-11-17. |
| FEMA National Risk Index (NRI) | The page in the brief, `hazards.fema.gov/nri/data-resources`, did not respond from this machine (connection failed). The data itself is available through FEMA's public map service: one query returns any county's figures as JSON. Release "December 2025". | Miami-Dade hurricane frequency 0.305 events a year; Harris (Houston) 0.184; Dallas 0.0115; Cook (Chicago) 0.0093. |
| Iowa Environmental Mesonet (IEM) warning archive, proposed by Claude | Reachable. Returns every past Weather Service warning for a latitude and longitude. A second service returns warnings whose drawn area covered the exact point. Terms: "You are free to use these services for any lawful purpose (including commercial...)". Coverage per IEM's dataset page: "Most WWA types back to 2008 or 2005". | Calendar days per year touched by a Winter Storm, Blizzard or Ice Storm Warning, 2016 to 2025: Minneapolis 6.3, Denver 4.6, Chicago 3.3, Dallas 1.4 (city-centre points, UTC days). |
| NOAA station observations through the ACIS web service, found during the check | Reachable. Returns measured daily snowfall and rainfall for a named station. Operated by the NOAA Regional Climate Centers. | Denver International Airport, 2025: 365 days, 1 missing, 19 with a trace, 26 with measurable snowfall (0.1 inch or more), 29.8 inches in total. |

### 4.2 Roles in the build

| Source | Role | Why this one |
|---|---|---|
| IEM warning archive | The score's main input for winter, flood and severe storms. | It measures how long an official "this is dangerous here" warning was in force, set locally by forecasters. It captures ice storms, which snowfall data misses. Commercial use is explicitly allowed. |
| FEMA NRI | Hurricane frequency. Also a cross-check figure for the other hazards. | Hurricanes are too rare for 10 years of data. FEMA's hurricane record runs from 1851 to 2024 (173.86 years, counted as distinct events, per its technical documentation). |
| NOAA station observations (ACIS) | Daily snowfall and rainfall questions, such as the Denver one. | It is measured, and it is the figure the Weather Service itself would quote. |

### 4.3 Sources rejected

- **Open-Meteo.** Rejected for two reasons. Its snowfall is modelled, and for Denver 2025 it disagrees with the airport measurement (33 or 43 days against 26). And its free tier forbids commercial use, which matters because the customer is a company.
- **National Weather Service API.** Not used in the core because it has no history. It stays a candidate for the alert bonus.
- **FEMA's headline risk scores and ratings.** Not used. They mostly reflect how much property and how many people a county has. Cook County (Chicago) scores 100 out of 100 for cold-wave risk, while its cold-wave loss rate, meaning expected yearly loss as a share of what is exposed with all loss types combined, sits at national percentile 4.9. Only FEMA's frequency figures are used.
- **NOAA Storm Events Database.** Not checked. It is a set of yearly bulk files with no query API, and the warning archive already answers the question.

## 5. The risk KPI: Expected Disruption Days per year

### 5.1 Definition

For each hub, the score is the number of **disruption days it should expect in an average year**, summed over four hazards. It is abbreviated EDD.

```
rate(hub, hazard)  = hours with a qualifying warning in force at the hub, 2016-2025, divided by 24, divided by 10
                     (days under warning per year)
EDD(hub, hazard)   = rate(hub, hazard) x weight(hazard)
EDD(hub, hurricane)= FEMA hurricane events per year for the hub's county x weight(hurricane)
EDD(hub, overall)  = sum of the four hazard EDDs
```

The whole calculation is plain Python over stored data. It runs and is unit-tested with no LLM and no network.

### 5.2 Inputs and sub-scores

| Hazard | What is counted | Warning types | Source | Period |
|---|---|---|---|---|
| Winter | Time with a warning in force for the hub's forecast zone | Winter Storm, Blizzard, Ice Storm, Lake Effect Snow (codes WS, BZ, IS, LE; warnings only) | IEM, warnings by point | 2016 to 2025 |
| Flood | Time with a warning whose drawn area covered the hub, plus time with a coastal warning for the hub's zone | Flash Flood (FF), Coastal Flood (CF); warnings only | IEM, both services | 2016 to 2025 |
| Severe storms | Time with a warning whose drawn area covered the hub | Tornado (TO), Severe Thunderstorm (SV); warnings only | IEM, storm-based warnings by point | 2016 to 2025 |
| Hurricane | FEMA's annualised frequency of hurricane events for the hub's county | not applicable | FEMA NRI field `HRCN_AFREQ` | 1851 to 2024 |

Rules for counting time:

- Time is counted, not calendar days. An 18-hour warning counts as 18 hours, whether or not it crosses midnight.
- Within one hazard, overlapping and repeated warnings are merged into one spell first, so no hour is counted twice.
- Each hour belongs to the calendar year it falls in, in the hub's own time zone.
- A record whose expiry is not after its issue time is skipped and reported in the data report.
- Watches and advisories do not count. Only warnings do.
- River flood warnings and long-running area flood warnings are excluded. In today's check a single point in Dallas was inside river flood warnings on 242 days in ten years, against 55 days for flash flood warnings. Counting them would swamp everything else with mostly minor, slow events.

Shown as supporting evidence but not scored: days under a Hurricane, Tropical Storm or Storm Surge Warning (recent history to set beside FEMA's long-run figure), and FEMA's frequency for the other three hazards (an independent cross-check).

### 5.3 Weights

The weight converts one counted unit into disruption days. The weights live in `config/scoring.toml`.

| Hazard | Weight | Unit | Reasoning |
|---|---|---|---|
| Winter | 1.0 | disruption days per day under warning | Neutral: the hub counts as disrupted for exactly as long as the warning is in force. |
| Flood | 1.0 | disruption days per day under warning | Same. |
| Severe storms | 1.0 | disruption days per day under warning | Same. |
| Hurricane | 5.0 | disruption days per event | Matches the recent record: time under Hurricane, Tropical Storm or Storm Surge Warnings in 2008 to 2025, divided by the events FEMA's frequency predicts for those years, is 4.4 days per event for Miami and 5.3 for Houston. Because that warning time includes tropical storms and storm surge, the weight makes FEMA's frequency reproduce time under any tropical warning. Whether FEMA's own count includes tropical storms is open point O3; it changes how to read the 5.0, per hurricane or per tropical system. |

The three warning weights are equal on purpose. They add no judgment about which hazard is worse: the measured length of the warnings already carries that. A winter storm warning lasts about 18 to 30 hours, a flash flood warning about 3, a severe thunderstorm warning under 1.

What the neutral weights leave out is aftermath: flooded roads that stay closed, power cuts, damage. No public data measures how long that lasts at a logistics hub. The company's own closure log would, and we do not have it. Until then an analyst who believes a hazard outlasts its warning uses the what-if in 5.5, and the stability test in 5.6 reports whether the ranking would change.

### 5.4 From score to ranking, and the bands

- Hubs are sorted by EDD, highest first. Rank 1 is the most exposed. Ties break by hub id.
- A ranking can be for one hazard or overall, and for all hubs or one region.
- Bands turn a figure into a word. They are fixed, so "high" means the same thing next year and when hubs are added.

The four bands are Low, Moderate, High and Very high. Their cut-offs are round numbers of days per year, **fixed at the milestone 2 review** from the twelve real figures, with the owner's sign-off and a line in the decision log. They do not move after that.

Setting cut-offs after seeing the figures means the labels describe how our own network spreads. That is acceptable because the ranking carries the decision and the label is only a word for it, but the agent's answers always give the figure beside the label.

### 5.5 What-if

`rank_hubs` accepts weight changes, either "multiply by" or "set to". The same scoring code runs with the changed weights. The result is flagged as a what-if, shown beside the official ranking, and never stored.

### 5.6 Confidence, computed in code

Every result carries a confidence label and a one-line reason, both produced by code. The model copies neither from memory.

| Test | How |
|---|---|
| Coverage | Share of expected data that is present: years with warning data, or station days that are not missing. |
| Separation | For each pair of neighbours in a ranking, is the gap between their yearly averages larger than the combined standard error of their ten yearly values? Hurricane figures have no yearly series, so they count as "not testable". |
| Weight stability | Overall rankings only. Recompute with each weight halved and doubled (8 variants). Are the top three hubs the same set every time? Does the top hub stay on top? |

- **High:** coverage at least 98%, every asserted gap passes separation, and (for overall rankings) the top three are stable.
- **Low:** coverage below 90%, or more than half the gaps fail separation, or the top hub changes when weights are halved or doubled.
- **Medium:** everything else.

For daily station statistics: high if at most 2% of days are missing, medium up to 10%, low beyond that.

### 5.7 What the KPI is not

- A warning is a forecast that conditions will be dangerous. It is not a record that the hub closed.
- EDD is in "day equivalents under our stated weights". It is not a prediction of closure days.
- It counts the time a warning was in force and nothing after it. Aftermath is not in the score.
- Ten years is a short record. Minneapolis's time under winter warnings ranged from none to 6.3 days in single years, around an average of 2.7 (city-centre test point, UTC years).
- Flood exposure at a real site depends on the exact parcel. This score sees only the hub's coordinates and county.

## 6. The hubs

The company is fictional, so the hub list is an assumption. Twelve hubs, each placed at its city's main airport. That is a realistic place for a distribution hub, and it puts the weather station at the hub.

| Region | Hubs (airport code) |
|---|---|
| Midwest | Chicago (ORD), Minneapolis (MSP), Kansas City (MCI), Indianapolis (IND), Columbus (CMH) |
| South | Miami (MIA), Houston (IAH), Dallas (DAL, Love Field), Atlanta (ATL), Memphis (MEM) |
| West | Denver (DEN), Phoenix (PHX) |

- Regions follow the US Census Bureau's regions. There is no hub in the Northeast.
- Dallas is the one exception to "main airport". It uses Love Field (DAL) instead of the larger Dallas/Fort Worth airport, on the expectation that Love Field keeps the hub, its station and its county inside Dallas itself. Milestone 1's county lookup confirms or corrects this.
- Phoenix is included on purpose as a quiet hub, so the ranking has a low end to sanity-check against.
- Coordinates, county and warning zone for each hub are **read from the data sources during milestone 1**, not typed from memory: coordinates from the station's own metadata, the county from a point query against FEMA's county layer, the zones from the warning archive's response. The point query against FEMA's layer is untested; if it does not work, the county comes from the county code in the warning data. Only Denver's station has been confirmed so far ("DENVER INTL AP").

## 7. Architecture

### 7.1 Components and how they talk

```
 Browser: one static chat page
     |  POST /api/chat  {session_id, message}        JSON over HTTP
     v
 API (FastAPI)  ---- keeps each conversation's history in memory
     |  agent.answer(session, message)                Python call
     v
 Agent loop  <------------------------------->  Claude (Anthropic Messages API)
     |    sends: question, history, tool list, answer schema
     |    receives: tool calls, then a final answer as JSON
     |  validated tool call                           Python call
     v
 Tools (6)  -->  Scoring core: pure functions, no network, no LLM
     |
     v
 SQLite file  <--  Ingest command  <--  IEM warnings, FEMA NRI, NOAA stations
                   (run ahead of time; raw responses kept on disk)
```

One question, end to end ("Which hubs in the Midwest are most exposed to winter disruption?"):

1. The browser posts the message to `/api/chat`.
2. The API finds or creates the session and calls the agent.
3. The agent sends Claude the system prompt, the conversation so far, the six tool definitions and the answer schema.
4. Claude replies with a tool call: `rank_hubs` with hazard `winter`, region `midwest`.
5. Code validates the arguments, runs the scoring core over the stored data and returns a result that includes a ready-made table and the provenance (sources, period, confidence).
6. Claude replies with the final answer as JSON: a short verdict, the ids of the tool results it relied on, and the order of hubs it asserts.
7. Code validates that JSON against the schema, then runs the cross-checks in 8.4. One repair attempt if anything fails, then a clear error.
8. Code builds the response: Claude's verdict, plus the table and the footnote taken directly from the tool result. The model never types a table or a footnote.

### 7.2 Choices, each with the main alternative rejected

| Choice | Alternative rejected | Why |
|---|---|---|
| **Data is fetched ahead of time into a local store. Tools read only the store.** | Tools call the public APIs live for each question. | Live calls take 2 to 5 seconds each, a university server could be down during the interview demo, and an evaluation over moving data cannot have fixed expected answers. The public APIs remain the source: the ingest command calls them. |
| **Our own agent loop on the Anthropic Messages API** (roughly 100 lines). | Anthropic's Managed Agents, where Anthropic hosts the loop and a sandbox. Also agent frameworks such as LangChain. | Our tools are local Python functions over a local database, we must expose our own API anyway, and the validate-and-repair step has to sit inside the loop where we control it. Managed Agents is in beta, bills session time and stores session history on Anthropic's side, none of which helps here. A framework would hide the schema enforcement the assignment asks us to show. |
| **Tables and footnotes are rendered by code from tool results.** The model writes only the verdict. | The model writes the whole answer and code checks it afterwards. | A number the model never types cannot be mistyped. The check in 8.4 then only has to police a few sentences of prose. |
| **One static HTML page served by the API.** | Streamlit or Gradio; a React app. | The assignment wants a chat interface that uses the agent's API. A static page with `fetch` is the smallest thing that does exactly that, with no build step and no JavaScript packages to install. |
| **Conversation history kept in memory, one server process.** | Sessions stored in the database. | Nothing in a demo needs a conversation to survive a restart. |
| **No streaming of the answer.** | Streaming tokens to the page. | The final answer is a JSON object that must be validated before anything is shown. The page shows a "working" indicator instead. |

## 8. Contracts between the LLM and our code

There are two directions. From the LLM to code: tool calls and the final answer. From code to the LLM: tool results. All are JSON with a schema, and all schemas are defined once as Pydantic models.

### 8.1 Tools (LLM to code)

Each tool is sent to Claude with `strict: true`, which makes the API guarantee the arguments match the schema. Code validates them again with Pydantic before running anything.

| Tool | Arguments | Returns |
|---|---|---|
| `list_hubs` | `region`: all, midwest, south, west | The hubs with city, state, region, station, county. |
| `rank_hubs` | `hazard`: overall, winter, flood, severe_storm, hurricane. `region`. `top_n` (integer or null). `weight_changes`: list of `{hazard, mode: multiply or set, value}`, empty for the official ranking. | Ranked rows with EDD, band, per-hazard breakdown, gap and ratio to the next hub, stability result. |
| `compare_hubs` | `hub_ids` (2 to 4). `hazards` (list). | Per hazard: each hub's rate and EDD, with the difference and ratio computed in code. Supporting evidence. |
| `explain_hub` | `hub_id` | Total EDD, band, rank, and per hazard: rate, weight, EDD, share of the total, best and worst year. Cross-check figures. |
| `daily_weather_stats` | `hub_id`. `metric`: snowfall, precipitation. `start_year`, `end_year` (integers or null; null means the last full calendar year, worked out in code). `threshold`: measurable, trace_or_more. | Days observed, days missing, days meeting the threshold, trace days, and the percentage. The period it resolved. |
| `get_methodology` | none | Weights, warning types per hazard, bands, period, sources, known limits. |

`hub_id` is an enumeration of the twelve ids. A city with no hub has no valid value, so the model cannot ask a tool about it and must answer "out of scope".

Example tool definition as sent to Claude:

```json
{
  "name": "daily_weather_stats",
  "description": "Measured daily snowfall or precipitation statistics for one hub's airport weather station. Use for questions such as 'what share of days had snowfall'. Covers 2016 to 2025 only.",
  "strict": true,
  "input_schema": {
    "type": "object",
    "properties": {
      "hub_id": {"type": "string", "enum": ["ORD","MSP","MCI","IND","CMH","MIA","IAH","DAL","ATL","MEM","DEN","PHX"]},
      "metric": {"type": "string", "enum": ["snowfall","precipitation"]},
      "start_year": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
      "end_year": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
      "threshold": {"type": "string", "enum": ["measurable","trace_or_more"]}
    },
    "required": ["hub_id","metric","start_year","end_year","threshold"],
    "additionalProperties": false
  }
}
```

### 8.2 Tool results (code to LLM)

Every tool returns the same envelope.

```json
{
  "ok": true,
  "tool": "daily_weather_stats",
  "data": {"hub_id": "DEN", "metric": "snowfall", "period": "2025", "days_observed": 364,
           "days_missing": 1, "days_meeting": 26, "days_trace": 19, "pct_of_observed": 7.1},
  "display": {"title": "Denver (DEN): days with measurable snowfall, 2025",
              "columns": ["Measure", "Value"], "rows": [["Days with 0.1 in or more", 26], ["..."]],
              "what_counts": "Measurable snowfall is 0.1 inch or more at the station."},
  "provenance": {"sources": ["noaa_station_acis"], "period": "2025", "data_as_of": "2026-11-24",
                 "confidence": "high", "confidence_reason": "1 of 365 days missing.", "is_what_if": false}
}
```

The figures in this example are today's real ones for Denver. A failure looks like `{"ok": false, "error": {"code": "no_data_for_period", "message": "Station data covers 2016 to 2025."}}` and is returned to the model as an error result, so it can tell the user instead of guessing.

### 8.3 The final answer (LLM to code)

Requested through the API's structured output feature, so the reply is guaranteed to be JSON of this shape, and validated again with Pydantic.

```json
{
  "status": "answered | out_of_scope | needs_clarification",
  "verdict": "One to four sentences of Markdown. No tables.",
  "evidence": ["<tool call id>", "..."],
  "hubs_ranked": ["MSP", "ORD"],
  "is_what_if": false,
  "caveats": ["Zero to three short sentences."]
}
```

- `evidence` lists the tool calls whose tables and footnotes the page should show, in order.
- `hubs_ranked` is the order the verdict asserts, most exposed first. Empty if it asserts none.

### 8.4 Validation, repair and the grounding check

After schema validation, code checks that the answer agrees with the tool results:

1. Every id in `evidence` is a real tool call from this conversation. If `status` is `answered`, `evidence` is not empty.
2. `hubs_ranked` contains only known hubs and matches the order in the cited ranking.
3. `is_what_if` is true exactly when a cited result is a what-if.
4. **Grounding.** Every number written in digits in `verdict` or `caveats` must match a number in the cited tool results or their arguments, allowing for rounding to the decimals shown. A number with no match fails.

If the schema or any check fails, the model gets **one repair attempt**: the errors are sent back and it answers again. If that also fails, the API returns `status: "error"` with a plain message. It never shows an unverified answer.

Other limits: at most 6 model calls per user message. A reply cut off by the token limit, or declined by the model's safety system, becomes a clear error. For the declined case the API offers a server-side fallback to another model; we turn it on if it combines cleanly with structured output, which the milestone 3 spike checks.

Known limit of the grounding check: it reads digits, not number words. "Roughly twice" is not caught. To reduce the need for the model to do arithmetic in words, the tools return differences and ratios ready-made, and the prompt tells the model to use only those.

### 8.5 API to chat page

`POST /api/chat` takes `{"session_id": "... or null", "message": "..."}` and returns:

```json
{
  "session_id": "...",
  "status": "answered | out_of_scope | needs_clarification | error",
  "verdict": "...",
  "tables": [{"title": "...", "columns": ["..."], "rows": [["..."]], "what_counts": "..."}],
  "footnote": {"sources": ["..."], "period": "2016-2025", "data_as_of": "2026-11-24",
               "confidence": "medium", "confidence_reason": "..."},
  "caveats": ["..."],
  "trace": {"model": "...", "tool_calls": [{"id": "...", "name": "...", "input": {}}],
            "repaired": false, "latency_ms": 0, "usage": {}}
}
```

Also `GET /api/hubs`, `GET /healthz`, and `GET /` for the page. The page shows `trace` in a collapsible "how this was computed" panel.

## 9. Which model the agent uses at runtime

The owner leans toward Claude through the Anthropic API. I agree: structured output and strict tool arguments are built into the API, which is exactly what the assignment's schema requirement needs.

The model's job here is bounded. It picks one of six tools, fills in a few arguments, and writes up to four sentences. It never produces a figure. Candidates, with prices from the Claude API reference bundled with Claude Code (cached 2026-11-03; to be re-checked against the live pricing page before they go in the README):

| Model | Input / output, USD per million tokens | Expectation |
|---|---|---|
| `claude-opus-5-5` | 4 / 20 | The current default model. Most reliable at following the "only numbers from tools" contract. Slowest of the three. |
| `claude-sonnet-5-5` | 2 / 10 | Built for everyday agent work. Likely enough for this job at half the price. |
| `claude-haiku-5-5` | 0.10 / 0.50 | Far cheaper and fastest. May be enough for six simple tools; unproven. |

**Recommendation: decide by measurement, not by argument.**

- Build and tune on `claude-opus-5-5`. If a check fails during development, the cause is then our prompt or tools, not the model's capacity.
- In milestone 5, run the evaluation unchanged on Sonnet 5.5 and Haiku 5.5.
- Ship the fastest, cheapest model whose score equals the best score and whose error and repair rates are no worse. The owner makes the final call from the table of quality, speed and cost.

The model id and effort level are settings, not code. Two facts from the reference shape the implementation: on Opus 5.5 and Sonnet 5.5 a tool call cannot be forced, so the final answer's shape comes from structured output and not from a forced "answer" tool; and thinking cannot be switched off on Opus 5.5, so speed is tuned through the effort setting.

## 10. Evaluation design

**Written before the agent exists** (milestone 2), so the agent is built to pass a fixed test and not the other way round.

### 10.1 The cases

Fourteen cases. Multi-turn cases run in one conversation.

| # | Question | What it tests |
|---|---|---|
| 1 | Which hubs in the Midwest are most exposed to winter disruption? | Assignment question. Ranking by one hazard and region. |
| 2 | Compare Miami and Houston in terms of hurricane and flood exposure. | Assignment question. Comparison across two hazards. |
| 3 | What percentage of days in Denver last year had snowfall? | Assignment question. "Last year" resolved in code. |
| 4 | Why is the Dallas hub's weather disruption risk high? | Assignment question. Explains drivers and states the real band, correcting the premise if Dallas is not high. |
| 5 | (after 1) And which is the least exposed? | Follow-up that keeps region and hazard from context. |
| 6 | (after 2) Which of the two is worse overall? | Follow-up that changes the hazard. |
| 7 | (after an overall ranking) What if a hurricane counted double? | What-if, flagged as such. |
| 8 | (after 7) Go back to the normal ranking. | The official weights were not changed. |
| 9 | Which three hubs are most exposed overall? | Overall ranking. |
| 10 | How is the score calculated, and what are the weights? | Methodology comes from the tool. |
| 11 | How exposed is our Seattle hub? | Out of scope: no such hub. No invented figures. |
| 12 | Will it snow in Chicago next week? | Out of scope: forecast. |
| 13 | Which hub is most at risk from earthquakes? | Out of scope: hazard not covered. |
| 14 | What percentage of days in Denver had snowfall in 2010? | Data does not cover the year. Says so, gives the covered range. |

### 10.2 The checks

All checks are code. No LLM judges another LLM. Each is reported separately, then combined.

| Check | Passes when |
|---|---|
| `status` | The answer's status is the expected one. |
| `tool` | The required tool was called with the key arguments, and no tool was called where none should be. It does not require an exact sequence. |
| `hubs` | `hubs_ranked` matches what the scoring code returns when the grader calls it directly on the same data. |
| `numbers` | The tables shown equal what the tool returns when the grader calls it with the arguments the case expects. That catches an answer about the wrong hub, year or hazard. Where a figure has been checked by hand against the source, the case pins that value, so a bug in our own tool is caught too. First pinned value: Denver International, 2025, 26 days of measurable snowfall out of 364 observed. |
| `mentions` | Required words are present (for example both hub names, or the band), and forbidden ones are absent (for example any dollar figure). |

A case passes when all its checks pass.

The evaluation does not re-test the grounding check from section 8.4. Any answer that reaches a grader has already passed it, so a grader reusing the same code would prove nothing. The grounding check has its own unit tests with planted wrong numbers (milestone 3), and the evaluation reports how often it forced a repair or an error.

### 10.3 Running and reporting

- One command: `uv run wra eval`. It prints a per-case table and a score, and saves every conversation, tool call and grader result under `evals/runs/<timestamp>/`.
- It calls the same `agent.answer()` function the API calls, so it tests what ships.
- The clock is pinned (`WRA_TODAY=2026-11-24`) so "last year" always means 2025 in the evaluation.
- A network or API failure is recorded as an error, separate from a wrong answer.
- It also reports the repair rate, error rate, time per answer, tokens and cost, all taken from the API's own usage figures.
- The graders have their own tests: a hand-written correct answer must pass every check, and an empty or wrong answer must fail.
- Reported result: 3 repetitions per case, because the same question can produce different wording and tool choices from run to run.

**Target:** the four assignment questions pass in all 3 repetitions, and at least 90% of all case runs pass.

**Limits, stated up front:** fourteen cases is a regression gate, not a fine instrument. At 14 cases and 3 repetitions the noise is roughly plus or minus 15 points, so small differences between models mean little. Prose quality is not graded automatically; the results document will include the four assignment answers in full for a human to read.

**Cost:** each evaluation run spends real API credit. My estimate is a few US dollars for 3 repetitions on Opus 5.5, and it is only an estimate. I will ask before the first paid run and report the measured cost after it.

## 11. Repository layout

```
weather-risk-agent/
  CLAUDE.md                  working rules for this repo
  README.md                  clone to running agent in a few commands
  pyproject.toml, uv.lock
  .env.example               placeholder only; the real .env is git-ignored
  .claude/settings.json      deny rule for reading .env
  config/
    hubs.toml                the twelve hubs
    scoring.toml             weights, warning types per hazard, bands, period, confidence thresholds
  src/wra/
    cli.py                   wra ingest | data-report | rank | ask | eval | serve
    ingest/                  iem.py, fema_nri.py, acis.py, store.py
    scoring/                 warning_time.py, kpi.py, confidence.py   (pure functions)
    tools/                   one module per tool, plus the registry
    agent/                   schemas.py, prompt.py, loop.py, grounding.py, render.py
    api/                     app.py, sessions.py, static/index.html
  evals/                     cases.py, graders.py, run.py, runs/
  tests/                     unit tests and recorded fixtures
  data/
    raw/                     responses as fetched from the public APIs (committed)
    wra.sqlite               built by `wra ingest` (git-ignored)
  docs/
    PLAN.md, ARCHITECTURE.md, ASSUMPTIONS.md, DECISIONS.md, EVAL_RESULTS.md, SUMMARY.md
    ai-session/              exported sessions and their index
  scripts/e2e.sh             the final end-to-end check
```

Alternative rejected: a separate front-end project beside a back-end project. One static page does not justify a second toolchain, and a single package keeps "clone to running" to a few commands.

Python 3.13, pinned for the project through `uv` (this machine's default is 3.14.4). Dependencies: `anthropic`, `pydantic`, `fastapi`, `uvicorn`, `httpx`, `python-dotenv`, and `pytest` for development. No JavaScript packages.

## 12. Data storage

**SQLite: one file, built by the ingest command.**

| Table | Holds |
|---|---|
| `hubs` | The twelve hubs with the coordinates, county and zones resolved at ingest. |
| `warning_events` | One row per warning: hub, type, level, issue and expiry times, issuing office, event number, whether it matched by zone or by drawn area. |
| `fema_nri` | The FEMA figures per hub county, with the release name. |
| `station_daily` | One row per hub per day: snowfall, precipitation, and the flags for trace and missing. |
| `fetch_log` | What was fetched, from which URL, when, with a checksum. |

- Raw warning events are stored, and the time under warning is computed from them by the scoring code. That keeps the counting rule in one tested place, and anyone can audit a figure back to individual warnings.
- The raw API responses are kept under `data/raw/` and committed. A fresh clone then builds the database in seconds without the network, the demo does not depend on a university server, and the evaluation's expected answers stay fixed. `wra ingest --refresh` fetches again.
- The ingest refuses to send a request with an empty coordinate and records which areas each response was for. Today's check showed why: a request with empty coordinates returned 926 records and no error.

Alternative rejected: Postgres, which needs a running server for a dataset of tens of thousands of rows read by one process. Also rejected: plain JSON files, which would push every filter and count into ad-hoc Python.

## 13. Milestones

Each milestone ends with a check that is run and pasted, not described. After each one: commit, update the assumptions and decision log, and a reminder to export the session before `/clear`.

**M0. Scaffold and rules.** `git init`, `uv` project, `CLAUDE.md` with the working rules from section 14, `.gitignore`, the `.env` deny rule, the docs skeleton, the work queue.
Check: `uv run pytest -q` passes one placeholder test. `git check-ignore -v .env` shows the rule. An attempt to read `.env` is refused.

**M1. Data.** Hub config, three ingest adapters, raw cache, SQLite.
Check: `uv run wra ingest --refresh` prints rows per source and hub. `uv run pytest tests/test_ingest_parsers.py -q` passes on recorded responses, including the empty-coordinate guard and a warning whose expiry is before its issue time (seen in today's data). `uv run wra data-report` prints, per hub, the station name, county, zones, row counts and share of missing station days, and confirms the county from FEMA agrees with the county code in the warning data.

**M2. Scoring core and the evaluation set. No LLM.** Merging warnings into spells and summing their time, rates, EDD, bands, ranking, what-if, confidence. The six tools as plain functions. The fourteen cases, the graders and the runner.
Check: `uv run pytest -q` passes, including hand-built warning lists with known answers (overlaps, duplicates, a warning that crosses New Year in the hub's time zone, an expiry before the issue time). `uv run wra rank overall` and `uv run wra rank winter --region midwest` print tables with no network. `uv run wra eval --agent stub` runs end to end and reports 0 of 14, while the grader tests show a correct answer passing and a wrong one failing.
Review point: I show the first real ranking of the twelve hubs. The owner fixes the band cut-offs, and they go in the decision log.

**M3. The agent.** Prompt, loop, schemas, validation, repair, grounding, a command-line chat.
First step is a spike: one live request proving that tool calls and a structured final answer work together on the chosen model. If they do not, the fallback is two steps: the tool loop without the output schema, then one final structured call that writes the answer.
Check: `uv run pytest tests/test_agent_loop.py tests/test_grounding.py -q` passes with a scripted fake model covering: valid answer; invalid then repaired; invalid twice gives an error; an ungrounded number triggers repair; a declined reply gives an error. `uv run wra ask "Which hubs in the Midwest are most exposed to winter disruption?"` prints a validated answer. `uv run wra eval` prints the score.

**M4. API and chat page.** FastAPI app, sessions, static page.
Check: `uv run pytest tests/test_api.py -q` passes. With the server running, `curl` posts a question, then a follow-up with the same session id, and the second answer uses the first. The owner opens the page and asks the four assignment questions; I give the steps and do not drive the browser.

**M5. Results and documents.** `uv run wra eval --reps 3`, the model comparison from section 9, `EVAL_RESULTS.md`, `README.md`, `ARCHITECTURE.md`, the one-page `SUMMARY.md`. Then a subagent with a fresh context reviews the whole diff against this plan and flags only gaps that affect correctness or the assignment's requirements. Fix what it finds.

**Final end-to-end check.** `scripts/e2e.sh` does the following and prints each result:

1. Clones the repository into a temporary folder. The clone has no `.env`, so the script points the cloned app at the original repository's `.env` through an environment variable (`WRA_ENV_FILE`). The key is never copied or printed.
2. `uv sync`, then `uv run wra ingest` from the committed raw responses, with no network.
3. `uv run pytest -q`.
4. Starts the server and, through the HTTP API only, asks the four assignment questions, one follow-up and one out-of-scope question.
5. Checks each response against the schema and its expected status, and checks the follow-up used the earlier context.
6. Runs `uv run wra eval --reps 3` and checks the score meets the target, which is defined over 3 repetitions.

**If time runs short, cut in this order:** the model comparison, the supporting-evidence figures (time under tropical warnings, FEMA cross-checks), page styling. The four assignment questions, the grounding check and the evaluation are never cut.

**Bonuses.** Only after the final check passes, and only after asking, in this order: deployment to a public URL, an alert when a hub's score changes, voice. Two notes for later. A public URL spends the owner's API credit on every message, so it needs an access guard before it goes up. And the alert has a natural trigger in this design: re-run the ingest, recompute, compare with the stored scores.

## 14. Working rules for the build

These go into `CLAUDE.md` in milestone 0 so they survive `/clear`.

- Numbers come from code, not from the model. The score is deterministic and unit-tested with no LLM. Weights live in a config file. Every number in an answer comes from a tool result.
- The LLM's output is validated against a JSON schema in code (Pydantic). Invalid output gets one repair attempt, then a clear error, never a guess.
- Show evidence, not claims. A milestone is done when its check passes, with the command and its output pasted.
- The evaluation set is written before the agent exists.
- Say what we do not know. `docs/ASSUMPTIONS.md` stays current. Answers state the data period, the sources and the confidence.
- A short decision log in `docs/DECISIONS.md`. Small commits with clear messages.
- Secrets live only in a git-ignored `.env`. Never read or print it. A deny rule in `.claude/settings.json` enforces this.
- Ask rather than guess. Push back when there is a better approach.
- Match the model to the task and say which was picked and why.
- The sessions are a deliverable. Remind the owner to export before every `/clear`. Keep `docs/ai-session/README.md` as the index. Never git-ignore `docs/ai-session/`.

Models for the build itself:

- This planning session ran on Fable, which suits open design questions.
- For milestones 0 to 4, I recommend the owner switch the main session to Opus: the work is implementation against a written spec.
- Review after each milestone: an Opus subagent with a fresh context.
- The final whole-diff review: a Fable subagent, because it is the single most consequential check.
- Today's data checks ran on Sonnet: four small, tightly specified fetch-and-report jobs.

## 15. Assumptions and open points

> This section is the list as it stood when the plan was approved. The live list is `docs/ASSUMPTIONS.md`; where they differ, that file wins.

Assumptions are choices made without data. They move to `docs/ASSUMPTIONS.md` in milestone 0.

| # | Assumption |
|---|---|
| A1 | The twelve hubs, their placement at main airports, and the Census regions (section 6). |
| A2 | A warning day stands in for a disrupted day. Warnings are forecasts, not closure records. |
| A3 | The warning types per hazard (5.2), including the exclusion of advisories, watches, cold and wind-chill warnings, high-wind warnings, and river and area flood warnings. |
| A4 | A day touched by a warning at all counts as one day, in the hub's time zone. |
| A5 | The four weights (5.3). Claude's judgment, not measured. |
| A6 | The band cut-offs at 2, 5 and 10 (5.4). |
| A7 | A day with warnings for two hazards counts once in each. A hurricane's flash flood warnings also count under flood. |
| A8 | Measurable snowfall means 0.1 inch or more. Trace days are reported separately. Missing days are left out of the percentage. |
| A9 | "Last year" means the last full calendar year by the server's clock. |
| A10 | The confidence thresholds (5.6). |
| A11 | Analysts accept waiting roughly 10 to 20 seconds for an answer. Not asked in the interview. |
| A12 | English only. |

Open points are facts not yet confirmed. Each has a milestone where it gets settled.

| # | Open point | Settled in |
|---|---|---|
| O1 | The ACIS station service publishes no usage terms on the two documentation pages I read. It is operated by NOAA's Regional Climate Centers. Whether committing its raw responses to the repository is acceptable is the owner's call. | M1 |
| O2 | A checker reported FEMA's FAQ as saying "This data may be used for commercial purposes." I did not re-read that document. I did confirm FEMA's required notice: "This product uses the Federal Emergency Management Agency's National Risk Index dataset API or downloadable datasets but is not endorsed by FEMA." It goes in the README and the page footer. | M5 |
| O3 | Whether FEMA's hurricane event count includes weaker tropical storms. | M1 |
| O4 | Whether tool calls and a structured final answer combine in one request the way the reference describes. | M3 spike |
| O5 | The size of the committed raw responses. If it is unreasonable for a repository, store only the fields we use. | M1 |
| O6 | Station ids for the eleven hubs other than Denver, and whether each has near-complete snowfall records. | M1 |
| O7 | Today's warning-day figures were computed in UTC at city-centre points. The build uses local days at airport points, so the figures will move somewhat. | M2 |

## 16. Risks

| Risk | Response |
|---|---|
| The weights are contested. | They are labelled as assumptions everywhere. The stability test reports whether the ranking depends on them, and the what-if lets anyone test their own. |
| The grounding check rejects good answers. | The evaluation measures the repair and error rates. If it proves too strict, we decide together whether to loosen the matching or downgrade a failure to a visible warning. |
| A data source is down during the demo. | The app reads only the local database, built from committed raw responses. |
| The same question gets different answers on different runs. | Tables and footnotes come from code and cannot vary. The evaluation runs each case three times. |
| Time. | The cut order in section 13. |

## Deviations

Changes forced by reality are appended here, newest last.

**2026-11-24, before any scoring code. How the score counts and weighs warnings (section 5).**

- *Planned:* count every calendar day a warning touches; weights of 1.0 (winter), 0.5 (flood) and 0.25 (severe storms) per such day and 5.0 days per hurricane event; bands at 2, 5 and 10.
- *What happened:* the owner asked how the weights were chosen before approving them. The honest answer was that the flood and storm weights were an ordering written as numbers, and that the only test applied was that Dallas came out "high", as the assignment's wording assumes. Measuring warning lengths in the archive then showed that flash flood warnings last about 3 hours and severe thunderstorm warnings under 1, so the weights overstated them roughly 4 and 7 times; and that counting calendar days touched turned Minneapolis's 27 days of winter warning time into 63.
- *Now:* count time under warning; all three warning weights are 1.0; the hurricane weight stays at 5.0, which the Miami and Houston records support; band cut-offs are fixed at the milestone 2 review. Dallas will probably not come out "high", and the agent will say so.
- *Lesson:* a number that happens to confirm the expected answer is the one to check hardest. The figures behind this entry are in `docs/ASSUMPTIONS.md`.

---

## Appendix A. Commands that reproduce today's checks

Run 2026-11-24. Each returned HTTP 200.

```
# Open-Meteo: Denver 2025 daily snowfall (unit cm)
curl -s "https://archive-api.open-meteo.com/v1/archive?latitude=39.7392&longitude=-104.9903&start_date=2025-01-01&end_date=2025-12-31&daily=snowfall_sum&timezone=America/Denver"

# National Weather Service: ask for alerts since 2025; only the last 7 days come back
curl -s -A "weather-risk-agent-check/0.1" "https://api.weather.gov/alerts?area=TX&start=2025-01-01T00:00:00Z&limit=500"

# FEMA National Risk Index, county layer: hurricane frequency for Miami-Dade
curl -s "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0/query?where=STCOFIPS%3D%2712086%27&outFields=STCOFIPS,COUNTY,NRI_VER,HRCN_AFREQ&returnGeometry=false&f=json"

# IEM: every warning for a point (Minneapolis), 2016-2025
curl -s "https://mesonet.agron.iastate.edu/json/vtec_events_bypoint.py?lat=44.9778&lon=-93.2650&sdate=2016-01-01&edate=2025-12-31"

# IEM: warnings whose drawn area covered a point (Dallas), 2016-2025
curl -s "https://mesonet.agron.iastate.edu/json/sbw_by_point.py?lat=32.7767&lon=-96.7970&sdate=2016-01-01&edate=2025-12-31"

# NOAA station observations (ACIS): Denver International, 2025 daily snowfall (inches; T = trace, M = missing)
curl -s "https://data.rcc-acis.org/StnData?sid=DEN&sdate=2025-01-01&edate=2025-12-31&elems=snow&meta=name,state,sids,ll&output=json"
```

Documents read for the quoted sentences: `open-meteo.com/en/terms`, `www.weather.gov/documentation/services-web-api`, `mesonet.agron.iastate.edu/api/`, `mesonet.agron.iastate.edu/info/datasets/vtec.html`, FEMA's National Risk Index technical documentation PDF (pages 51, 89 to 90, 218, 397 and 432), and the licence text on FEMA's National Risk Index map service item.
