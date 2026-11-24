# Work queue

Most important first. Each line points to where the item's state lives; the state itself is not kept here.

Order re-checked against the assignment on 2026-11-24 (see the second entry under Deviations in `docs/PLAN.md`).

## Queue

- [q10] Deployment to a public URL, ask first. The assignment calls it preferred, so it stands apart from the bonuses. A public URL spends the owner's API credit on every message, so it needs an access guard. → `docs/PLAN.md` section 13
- [q21] Run the README's page check by hand before a demo (owner; one paid question, under a cent on Haiku). → `.claude/OPEN_ISSUES.md`, "The page's own logic has no automated test"
- [q19] Owner decision: the queue guard also refuses a line under Done / Dropped without "Done <date>" or "dropped" (an open item was filed under Done in session 05 and the guard let it through). → `.claude/hooks/queue-guard.py`
- [q20] Owner decision on two global `~/.claude/CLAUDE.md` lines from session 05: (a) a subagent cannot write .md files, so it returns the text and the main session saves it; (b) before a commit, every file the message names is staged (a README change was left out of a commit whose message claimed it, amended before push). Edit only on the owner's word. → `~/.claude/CLAUDE.md`
- [q8] Bonuses, ask first: score-change alert, voice. → `docs/PLAN.md` section 13

## Done / Dropped

- [q18] Final end-to-end check re-run on the shipped code. Done 2026-11-25. Proof: `scripts/e2e.sh --paid` passed on `27c5b6d` (360 tests in a fresh clone, 6 of 6 API questions, `wra eval --reps 3` 42 of 42, none refused or repaired, target met; 0.043 USD for the evaluation from its run record plus about 0.01 for the API questions); the owner ran it with `!` after the auto-mode permission check refused it again. Run record `20261124T234915Z-claude` and the doc updates are in the commit that moves this line.
- [q17] Session 05 transcript committed. Done 2026-11-25. Proof: commit `3339d36`; the work-address check, the session-link search (`claude\.ai/code/session_[A-Za-z0-9]`) and a search for key-like text (`sk-ant-`) all printed 0 on the file before it was committed.
- [q6] Milestone 5: results, documents, fresh-context review, final end-to-end check. Done 2026-11-25. Proof: `scripts/e2e.sh --paid` passed on `1b455ab` (354 tests in a fresh clone, 6 of 6 API questions, `wra eval --reps 3` 42 of 42, target met, about 0.05 USD; run `20261124T232102Z-claude`), and again on `27c5b6d` after the hazard order field (q18); `docs/EVAL_RESULTS.md`, `docs/ARCHITECTURE.md`, `docs/SUMMARY.md`; the Fable review's eight findings fixed in `1b455ab`; the owner chose Haiku 5.5 (decision log).
- [q13] Terms explained where they appear. Done 2026-11-25. Proof: commit `cca0acd` (21 tests, 331 passed on that tree); a live `wra ask` on Denver snowfall explained "measurable" and "trace" in plain words (0.041 USD, session 05), as did the shipped model's answer in `docs/EVAL_RESULTS.md`; the owner confirmed the answers read right.
- [q16] How the page's own logic is checked. Done 2026-11-24. Proof: the owner chose a written check by hand; it is in `README.md`, "Checking the page by hand before a demo", added in the commit that moves this line. Running it before the demo stays open in `.claude/OPEN_ISSUES.md`.
- [q15] Two instruction wordings from session 04. Done 2026-11-24. (a) Project `CLAUDE.md` rule 6 now says a commit message's claims hold for the tree being committed: edited on the owner's word, proof in the commit that moves this line. (b) "Or a record" in the global file's "Recheck assumptions" line: dropped on the owner's word, 2026-11-24.
- [q14] Session 04 transcript committed. Done 2026-11-24. Proof: commit `08395e9`; the work-address check and the session-link search (`claude\.ai/code/session_[A-Za-z0-9]`) both printed 0 on the file before it was staged.
- [q5] Milestone 4: API and chat page. Done 2026-11-24. Proof: commits `ac1912e` to `772b0d6`; `uv run pytest -q` 309 passed on `772b0d6`; a question and its follow-up by curl through the running API (the follow-up made no tool call and cited the first turn's result; 0.046 USD); the owner asked the four assignment questions in the page and reported everything looked right, and tried the server-restart path by hand; all in session `04-api.txt`.
- [q12] Session 03 transcript committed. Done 2026-11-24. Proof: commit `170d557`. The one match for "claude.ai/code/session_" is the handoff quoting that search text; no real link.
- [q4] Milestone 3: the agent. Done 2026-11-24. Proof: commits `406d78b` to `097adfb`; `wra eval` on `097adfb` passed 14 of 14 with no repairs (0.53 USD), loop and grounding tests on a scripted fake model, `wra ask` live; all in this session's transcript.
- [q3] Milestone 2: scoring core and evaluation set. Done 2026-11-24. Proof: commits `e618353` to `b31c2a5`; the checks, run on `b31c2a5` in a clean checkout with the network blocked, are in this session's transcript (203 tests passed, `wra eval --agent stub` 0 of 14).
- [q11] Session 02 transcript committed. Done 2026-11-24. Proof: commit `9d551f5`.
- [q2] Milestone 1: data. Done 2026-11-24. Proof: commits `5e67c19` to `d127f5b`; the checks' output is in session `02-data.txt`.
- [q9] Session 01 transcript committed. Done 2026-11-24. Proof: commit `4adbf00`.
- [q1] Milestone 0: scaffold and rules. Done 2026-11-24. Proof: commits `db31520`, `14817f0`, `e427e7b`; the three checks' output is in session `01-plan.txt`.
- [q7] Owner decision: how the score counts and weighs warnings. Done 2026-11-24. Proof: the entry "Count time under warning, with equal weights for the three warning hazards" in `docs/DECISIONS.md`. The band cut-offs it leaves open are part of q3.
