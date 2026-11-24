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
