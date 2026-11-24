# AI session record

The full Claude Code sessions behind this project, exported by the owner with `/export` before each `/clear`. Files are numbered in the order the work happened.

| File | What it covered |
|---|---|
| `01-plan.txt` | Interview with the owner, live checks of five data sources, the plan, a review of the proposed weights against measured warning lengths, and milestone 0 (repository scaffold and working rules). |
| `02-data.txt` | The order of work re-checked against the assignment, then milestone 1: the hub list, parsers for the three sources written test-first on recorded responses, the fetch step and the offline database build, the data report and what it showed, and two independent reviews whose findings led to a wider warning request, three more checks in the build and fifteen more tests. Also a fix to the handoff skill so the next session's prompt is saved and shown to that session when it starts. |
| `03-scoring-and-agent.txt` | Milestones 2 and 3. The score: warning time merged per hazard and split by local year, test-first on hand-built warning lists, then the first real ranking and the review point (band cut-offs, coastal and area flood warnings, FEMA's hurricane defaults, a check of published evidence on whether some hazards disrupt more than their warning time shows). Confidence rules, the six tools, the fourteen evaluation cases and their graders. Then the agent on Claude Opus 5.5: a spike, the loop with validation, repair and grounding, the first paid evaluation runs, and two fresh-context reviews whose findings were checked against the code and fixed, with the owner deciding every rule that changes what counts as a valid answer. |
