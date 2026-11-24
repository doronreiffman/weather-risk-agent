# Work queue

Most important first. Each line points to where the item's state lives; the state itself is not kept here.

Order re-checked against the assignment on 2026-11-24 (see the second entry under Deviations in `docs/PLAN.md`).

## Queue

- [q14] Commit the session 04 transcript once the owner has exported it as `docs/ai-session/04-api.txt`. → `docs/ai-session/README.md`
- [q13] Answers use terms without explaining them, such as "trace day" (owner, milestone 4 page check). Settle it before milestone 5's paid runs, so they measure the final wording. → `docs/ASSUMPTIONS.md` O15
- [q6] Milestone 5: results, documents, fresh-context review, final end-to-end check. Measures verdict length. → `docs/PLAN.md` section 13, `docs/ASSUMPTIONS.md` O14
- [q10] Deployment to a public URL, ask first. The assignment calls it preferred, so it stands apart from the bonuses. → `docs/PLAN.md` section 13
- [q8] Bonuses, ask first: score-change alert, voice. → `docs/PLAN.md` section 13

## Done / Dropped

- [q5] Milestone 4: API and chat page. Done 2026-11-24. Proof: commits `ac1912e` to `772b0d6`; `uv run pytest -q` 309 passed on `772b0d6`; a question and its follow-up by curl through the running API (the follow-up made no tool call and cited the first turn's result; 0.046 USD); the owner asked the four assignment questions in the page and reported everything looked right; all in session `04-api.txt`.
- [q12] Session 03 transcript committed. Done 2026-11-24. Proof: commit `170d557`. The one match for "claude.ai/code/session_" is the handoff quoting that search text; no real link.
- [q4] Milestone 3: the agent. Done 2026-11-24. Proof: commits `406d78b` to `097adfb`; `wra eval` on `097adfb` passed 14 of 14 with no repairs (0.53 USD), loop and grounding tests on a scripted fake model, `wra ask` live; all in this session's transcript.
- [q3] Milestone 2: scoring core and evaluation set. Done 2026-11-24. Proof: commits `e618353` to `b31c2a5`; the checks, run on `b31c2a5` in a clean checkout with the network blocked, are in this session's transcript (203 tests passed, `wra eval --agent stub` 0 of 14).
- [q11] Session 02 transcript committed. Done 2026-11-24. Proof: commit `9d551f5`.
- [q2] Milestone 1: data. Done 2026-11-24. Proof: commits `5e67c19` to `d127f5b`; the checks' output is in session `02-data.txt`.
- [q9] Session 01 transcript committed. Done 2026-11-24. Proof: commit `4adbf00`.
- [q1] Milestone 0: scaffold and rules. Done 2026-11-24. Proof: commits `db31520`, `14817f0`, `e427e7b`; the three checks' output is in session `01-plan.txt`.
- [q7] Owner decision: how the score counts and weighs warnings. Done 2026-11-24. Proof: the entry "Count time under warning, with equal weights for the three warning hazards" in `docs/DECISIONS.md`. The band cut-offs it leaves open are part of q3.
