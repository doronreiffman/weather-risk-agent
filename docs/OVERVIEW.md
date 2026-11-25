# Weather Risk Intelligence Agent: overview

**The assignment.** A logistics company picks a few of its distribution hubs each year for resilience upgrades, and its analysts need to know which hubs are most exposed to weather disruption. The brief asked for an AI agent that answers questions such as "Which hubs in the Midwest are most exposed to winter disruption?" and "Why is the Dallas hub's weather disruption risk high?". The agent had to use public data, rank hubs by a defined measure with deterministic logic, explain its reasoning and handle follow-ups. It also needed a chat page with an API behind it, a JSON schema between the model and the code, an evaluation set, and plain statements of assumptions and uncertainty.

**The measure.** Each hub gets **expected disruption days a year**: the time it spent under National Weather Service warnings for winter weather, flash floods and severe storms in an average year from 2016 to 2025, plus 5 days for each hurricane or tropical storm FEMA expects in its county each year. Plain Python computes it, with the weights in a config file and fixed bands from Low to Very high. Code also rates the ranking's confidence. Today it is low, because most neighbouring hubs are too close to separate, and the agent says so.

**What was built.**

- **Data:** twelve fictional hubs and three public sources: warnings from Iowa State University's archive, hurricane figures from FEMA's National Risk Index, and daily snowfall and rainfall from NOAA weather stations. The raw responses are committed, so the database is rebuilt offline.
- **The agent:** Claude Haiku 5.5 reads the question, calls six tools (rank, compare, explain, daily statistics, what-if, method) and writes a short verdict. Code checks every answer against a schema and every number against the tool results. A failing answer gets one repair attempt, then a plain error. Code, not the model, writes the tables.
- **Chat page and API:** a FastAPI server and a one-file page. Follow-ups keep their context. A city with no hub, a forecast or a request for investment advice gets a plain "out of scope".
- **Evaluation:** fourteen questions with automatic checks (the brief's four, follow-ups and out-of-scope cases), each asked three times. The final run from a fresh clone passed 42 of 42. Opus 5.5 also passed all 42 at about 27 times the cost, so Haiku was chosen. An answer costs well under a cent.
- **Bonuses:** a public website behind a sign-in and a daily limit; a weekly GitHub job that opens an issue when a hub's score changes; spoken questions, where the browser turns speech into text, the analyst checks the words before sending, and the server never receives audio.

**Key choices.** Exposure means weather at the hub's location only: a fictional company has no real business figures, so none were invented. Time under warning counts, not days touched, so a long warning weighs more than a short one. The agent ranks and explains but never recommends; asked where to invest, it names what the decision still needs. The scope is narrow on purpose: four hazards, done well.

**What it cannot tell.** A warning is not a record that a hub closed. The measure describes the past and does not forecast. It sees each hub's county, not the flood risk at the exact site. Hub importance, upgrade costs and the company's own closure records are still needed before money is spent.

**Further reading:** the README (how to run it, on the public site or locally), `docs/SUMMARY.md` (for the analysts' manager), `docs/ARCHITECTURE.md` (components, repository, data storage), `docs/EVAL_RESULTS.md` (the evaluation) and `docs/ai-session/` (the full AI sessions).
