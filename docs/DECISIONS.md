# Decision log

Short entries for choices that shape the rest of the build. Details and evidence are in `docs/PLAN.md`; this file says what was decided, why, and what was turned down. Entries are never edited; a later decision that replaces one says so.

## 2026-11-24 — Exposure means weather at the location only

**Decision:** The score measures weather exposure alone. It does not include how important a hub is, and the agent ranks and explains without recommending where to invest.
**Why:** The company is fictional, so any business figure would be invented and the ranking would rest partly on made-up numbers. Rejected: scaling by an importance figure; naming an investment shortlist.
**Context:** Owner's interview answers 1 and 9. Plan sections 2 and 3.

## 2026-11-24 — Score hubs by official warnings, not weather thresholds or FEMA's ratings

**Decision:** A hub's exposure to winter weather, flooding and severe storms is measured from National Weather Service warnings in force at the hub in 2016 to 2025. Hurricanes use FEMA's annualised frequency, which rests on a record from 1851 to 2024.
**Why:** Warnings are set locally by forecasters, so they track what is dangerous in that place and they capture ice storms. Rejected: our own thresholds on modelled daily weather (Denver 2025 had 43, 10 or 1 snow days depending on the cut-off); FEMA's risk scores and ratings (they mostly reflect how much property and how many people a county has).
**Context:** Owner's interview answers 4 and 5. Plan sections 4 and 5. How the warnings are counted and weighed is the last entry in this file.

## 2026-11-24 — Three data sources; Open-Meteo and the Weather Service API left out

**Decision:** Use the Iowa State warning archive, FEMA's National Risk Index and NOAA airport station records (ACIS).
**Why:** Each was tested live. Open-Meteo, named in the brief, was dropped because its snowfall is modelled and disagrees with the airport measurement, and its free tier forbids commercial use. The Weather Service API keeps only 7 days of alerts, so it cannot support a long-run ranking.
**Context:** Owner's interview answer 7. Plan section 4 and Appendix A. The owner accepted committing the raw station responses although that service publishes no usage terms (open point O1).

## 2026-11-24 — Data is fetched ahead of time into SQLite; tools never call the network

**Decision:** An ingest command fetches from the public APIs, keeps the raw responses in the repository and builds a local SQLite file. The agent's tools read only that file.
**Why:** Answers are fast and repeatable, the live demo does not depend on a university server, and the evaluation can have fixed expected answers. Rejected: calling the APIs live for each question; Postgres; plain JSON files.
**Context:** Plan sections 7.2 and 12.

## 2026-11-24 — Our own agent loop on the Anthropic Messages API, with tables rendered by code

**Decision:** A small loop we own calls Claude with six strictly typed tools and a schema for the final answer. The model writes only a short verdict; code renders the tables and the data, period and confidence lines from the tool results, and checks every digit in the verdict against those results.
**Why:** The validate-and-repair step has to sit inside a loop we control, and a number the model never types cannot be mistyped. Rejected: Anthropic's Managed Agents (beta, bills session time, and our tools are local functions over a local database); agent frameworks; letting the model write the whole answer.
**Context:** Plan sections 7 and 8.

## 2026-11-24 — The runtime model is chosen by the evaluation

**Decision:** Build and tune on `claude-opus-5-5`, then run the same evaluation on Sonnet 5.5 and Haiku 5.5 and ship the fastest, cheapest model whose results are no worse. The owner makes the final call from the measured table.
**Why:** The model's job is bounded, so a cheaper model may be enough, but that is a claim to measure and not to assume. Model and effort level are settings, not code.
**Context:** Owner's approval on 2026-11-24. Plan section 9.

## 2026-11-24 — Count time under warning, with equal weights for the three warning hazards

**Decision:** A hazard's rate is the hours a qualifying warning was in force at the hub, divided by 24, per year. Winter, flood and severe storms each weigh 1.0. A hurricane weighs 5.0 days per event. Band cut-offs are fixed at the milestone 2 review from the twelve real figures.
**Why:** The first proposal counted every calendar day a warning touched and weighed winter 1.0, flood 0.5 and storms 0.25. The owner asked how those numbers were chosen. They were an ordering written as numbers, tested only by Dallas coming out "high". Measured warning lengths (winter storm 18 to 30 hours, flash flood 3, severe thunderstorm under 1) showed the flood and storm weights overstated them about 4 and 7 times, and the day rule turned Minneapolis's 27 days of winter warning time into 63. Equal weights add no judgment: the measured length of the warnings carries the difference between hazards. The hurricane figure is kept because the Miami and Houston records support it (4.4 and 5.3 days under tropical warnings per expected event). Rejected: keeping the original proposal; building both rules and choosing after seeing which story each tells.
**Context:** Owner's choice on 2026-11-24. Evidence in `docs/ASSUMPTIONS.md`. Plan section 5 and its Deviations entry. Aftermath beyond the warning is not scored; analysts test it with the what-if.

## 2026-11-24 — A hub's place comes from its station's coordinates, and wrong-place data stops the build

**Decision:** A hub sits at the coordinates its airport weather station reports. Its county is the one whose outline contains that point, as FEMA's map and the Weather Service's map both give it. The offline build stops if a stored response was changed after it was fetched, answers a different request than today's (another point or period), or names an area in another state. A county disagreement between the two maps does not stop the build; the data report shows it and exits with an error.
**Why:** Data for the wrong place looks exactly like data for the right one: a request with empty coordinates returned 926 records and no error. So "which place is this for" is checked by code on every build. Rejected: typing coordinates or counties by hand; taking the county from the station service's own label, which names the neighbouring county for O'Hare (Cook, where the point is in DuPage) and Atlanta (Fulton, where the point is in Clayton).
**Context:** Milestone 1. `src/wra/ingest/build.py`, `src/wra/ingest/points.py`. Figures in `docs/ASSUMPTIONS.md`, milestone 1 section. Made by Claude during the build and reported to the owner the same session.

## 2026-11-24 — A warning issued for a whole zone counts only for a hazard that covers the zone

**Decision:** Coastal flood warnings leave the flood score. Flood counts flash flood warnings whose drawn area covered the hub. Zone-issued warnings still count for winter weather.
**Why:** The plan counted any coastal flood warning for the hub's forecast zone. The only two in ten years, at Houston in 2016, went to the whole Harris zone, and their text names flooding only along Galveston Bay and the Gulf beaches. A snowstorm covers a zone; coastal flooding stays at the shore, so a zone match overstates it. This is the same reasoning that already scores flash floods and storms from drawn areas, not county rows. Rejected: keeping them as the approved rule said (Houston's flood figure 0.72 instead of 0.47 days a year, 4th overall instead of 7th).
**Context:** Owner's choice at the milestone 2 review. Evidence in `docs/ASSUMPTIONS.md`, milestone 2 section, point 3. `config/scoring.toml`.

## 2026-11-24 — Band cut-offs at 1, 2 and 3 days a year, for overall figures only

**Decision:** A hub's overall figure is Low below 1 expected disruption day a year, Moderate from 1, High from 2 and Very high from 3. Single-hazard figures get no band. The cut-offs do not move.
**Why:** The twelve figures run from 0.42 (Phoenix) to 2.90 (Minneapolis). Equal one-day steps are the plainest round grid at that scale, chosen without aiming at any hub. Very high is empty today, which leaves room for a hub worse than any we have. Dallas (2.02) is High by 0.02 days, so its answer says how close that is. Bands on single hazards were rejected because a hub could then be Moderate on every hazard and High overall. Rejected cut-offs: 1 / 2.5 / 4 (only Minneapolis High) and 1 / 3 / 5 (no hub High); also rejected: no bands at all.
**Context:** Owner's choice at the milestone 2 review, from the ranking in `docs/ASSUMPTIONS.md`, milestone 2 section. `config/scoring.toml`.

## 2026-11-24 — Weights stay equal; winter's longer road effect is shown as a fixed note

**Decision:** Winter, flood and severe storms keep weight 1.0. Wherever winter figures count, code adds a note that winter's road effect outlasts its warning and the score may understate it, and an overall ranking reports its top three with winter counted double.
**Why:** The owner asked whether some hazards disrupt more than others. Published studies, checked against their text, show winter's effect on truck speeds lasts longest after the event (FHWA-HOP-16-044, 2016: almost 8 mph below normal four hours after ice and snow) and that hurricane power cuts run longest (PNNL-33340, 2022). None measures disruption in days per day under warning, so none gives a weight. With winter at 1.5 or 2.0 Minneapolis stays first and the same five hubs stay on top. Rejected: winter at 1.5 or 2.0 as a stated judgment.
**Context:** Owner's choice on 2026-11-24. Evidence in `docs/ASSUMPTIONS.md`, milestone 2 section. Replaces nothing: it confirms the weights in the entry "Count time under warning, with equal weights for the three warning hazards".

## 2026-11-24 — An answer's evidence cites result ids our code assigns

**Decision:** Every tool result carries a short `result_id` (R1, R2, ...) in its content, numbered across the conversation, and the final answer's `evidence` must cite those ids. The page shows the tables of exactly the cited results.
**Why:** The milestone 3 spike showed the model citing an id it invented, because the API's tool-use ids sit in its own output, not in the results it reads. An id the model can see in the result is one it can copy, and the code can check every cited id against the results it holds. Rejected: citing the API's tool-use ids (the spike's failure); a schema rebuilt per request with the valid ids as an enumeration (a new schema each time costs a compilation and breaks the prompt cache).
**Context:** `src/wra/agent/loop.py`, `src/wra/agent/checks.py`. Plan section 8.3 and the milestone 3 entry under Deviations.

## 2026-11-24 — The agent loop, not the SDK, retries model calls, inside a time limit per message

**Decision:** The SDK's own retries are off. The agent loop retries a failed call once, under the SDK's rule for which failures to retry; each attempt waits at most 60 seconds or the time left of the message's 90, and a wait the API asks for that does not fit ends the message with a plain error.
**Why:** The owner chose a 90-second limit per message: a message can make 6 calls, so limits per call alone let a slow API hold the page, and the conversation's lock, for about 12 minutes. The SDK gives every attempt the same timeout and sleeps as long as a `retry-after` header asks, with no upper bound, so no SDK setting keeps a message inside a limit. Rejected: keeping the SDK's retry and halving each attempt's timeout (a long `retry-after` still breaks the limit); a timer around the whole message in the API (the work and the conversation's lock would carry on after the page had its error).
**Context:** `src/wra/agent/loop.py` (`_call`, `_retry_wait`), `config/agent.toml`. Evidence in `docs/ASSUMPTIONS.md`, milestone 4 section, point 2. Keeps O13's values (60 seconds per call, one retry) and replaces how they are applied.

## 2026-11-24 — The API sends every agent reply with one body, and the HTTP status says only which kind of failure

**Decision:** `POST /api/chat` always returns the agent's reply object. It is 200 unless the reply is an error; then busy is 409, a conversation the server does not hold is 404, and every other failure (the model unreachable, too slow, declined, cut off, invalid twice, out of calls) is 502. The status is chosen from the reply's `error_code`, never from its message.
**Why:** The owner chose it from three options. A failure then shows in the server log and stops `curl --fail`, which the planned end-to-end script can use, and the page still reads one shape whatever the status. Rejected: 200 for everything (a failing model looks healthy in the log); one status for every failure (busy and model-down look the same).
**Context:** `src/wra/api/app.py`, `src/wra/agent/schemas.py` (`ErrorCode`). `docs/ASSUMPTIONS.md`, milestone 4 section, points 1 and 3.

## 2026-11-24 — A bug in the agent's own code is HTTP 500; three corrections to the two entries above

**Decision:** An exception from our own code while answering removes the turn, as any failure does, and returns a reply with `error_code` `internal_error`, sent as HTTP 500.
**Why:** The milestone 4 review showed that such an exception gave a bare 500 and left the half-finished turn in the conversation, where the model would see it on the next message. 500 and not 502, because the owner's 502 covers failures on the model's side and this one is ours. Corrections, found by the same review and checked against the sources: the SDK's wait for `retry-after` is capped, at 4,294,967 seconds (about 49.7 days), not unbounded; the 90-second limit is close to a ceiling, not exact, because the HTTP library applies a timeout to each stage of a call; and a malformed request gets FastAPI's 422 validation message, not the reply object.
**Context:** `src/wra/agent/loop.py` (`answer`, `_roll_back`), `src/wra/api/app.py`. `docs/ASSUMPTIONS.md`, milestone 4 section, points 2 and 5. Claude's choice, reported to the owner and open to change.

## 2026-11-25 — The agent ships on Claude Haiku 5.5

**Decision:** `config/agent.toml` names `claude-haiku-5-5` at effort `medium`, with the server-side refusal fallback off.
**Why:** The owner chose it from milestone 5's comparison of the same evaluation on three models. Haiku passed 41 of 42 case runs with no answer refused, its one miss a right answer that wrote a weight as a word; Opus 5.5 passed 42 of 42 at about 27 times the cost per answer (2.0 cents against 0.074); Sonnet 5.5 missed the target, repeating identical tool calls until the call limit. Rejected: Opus, which section 9's rule (equal score) would have kept, because the owner found its cost too high for one case run's difference; Sonnet, whose extra calls brought its cost close to Opus's on the questions it struggled with. The fallback is off because Haiku 5.5 has none (Claude API reference, Migrating to Claude Haiku 5.5).
**Context:** `docs/EVAL_RESULTS.md`, `docs/ASSUMPTIONS.md` milestone 5 section, `config/agent.toml`. Switching back is a config change (`WRA_MODEL` or the file) plus an evaluation run.

## 2026-11-25 — A claim the prose cannot reliably carry becomes a checked field of the answer

**Decision:** For a comparison across several hazards, the final answer states each hazard's order in `hazard_orders`, which code checks against the cited result (one repair if wrong), and the comparison table carries a code-written note saying which hub leads each hazard.
**Why:** The final review showed a swapped comparison ("Houston leads on hurricanes at 1.52") passes the number checks, since every figure is still in the result. A grader reading the pairing from word positions in the prose was built and then dropped at the handoff review: a right answer phrased "Houston's hurricane exposure is lower than Miami's" would fail it, and any word rule moves the misses elsewhere. The owner chose the structured claim plus the code note. Rejected: loosening the word rule; recording the limit only; a model judging the answer (the plan rules out a model grading a model). Same pattern as `hubs_ranked`: the remaining gap is prose that contradicts its own structured claim, and the code note keeps the true fact on the page.
**Context:** `src/wra/agent/schemas.py` (`HazardOrder`), `src/wra/agent/checks.py` (`_hazard_order_problems`), `src/wra/evals/graders.py` (`_leads`), `src/wra/tools/compare_hubs.py`. `docs/ASSUMPTIONS.md`, milestone 5 section, point 6.

## 2026-11-25 — Public mode is decided by the listen address and fails closed

**Decision:** `wra serve` on any address but this machine's own is public mode: it refuses to start without `WRA_ACCESS_CODE`, puts HTTP Basic sign-in in front of every route but `/healthz`, and gives the agent a limit of 100 questions a UTC day; the site runs on a Koyeb free instance from a Dockerfile.
**Why:** A public URL spends the owner's API credit on every message, and the reviewers may use it alone. Tying the mode to the address means a deploy with a missing secret fails instead of opening the site. The browser's own sign-in box needs no change to the page, whose logic is checked only by hand; a code field on the page was rejected for that reason. The limit is handed to the agent, not checked in the API layer as the design first said, because a refusal on a new conversation must carry a conversation id the agent holds (the page keeps the id an error reply carries); only `wra serve` in public mode hands it over, so `wra ask`, `wra chat` and `wra eval` never meet it. The count lives in memory and starts again on each restart, so the hard ceiling is a separate Anthropic workspace with its own monthly limit. Host (owner's choice): Koyeb's free instance, over Fly.io's free allowance (more setup, a spare machine by default that would split conversations), Render paid (about $3.30 for two weeks, never sleeps) and Render free (about a minute to wake). Its 0.1 of a CPU makes a start after an idle hour slow (about 42 seconds measured locally at that size); the owner re-evaluates once it is measured on Koyeb.
**Context:** `docs/DEPLOY_DESIGN.md`, `docs/DEPLOY_PLAN.md`; `src/wra/api/public.py`, `src/wra/agent/limits.py`, `src/wra/agent/loop.py`, `src/wra/cli.py` (`_serve`), `Dockerfile`, `.dockerignore`.
