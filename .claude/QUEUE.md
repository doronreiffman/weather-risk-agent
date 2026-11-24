# Work queue

Most important first. Each line points to where the item's state lives; the state itself is not kept here.

Order re-checked against the assignment on 2026-11-24 (see the second entry under Deviations in `docs/PLAN.md`).

## Queue

- [q3] Milestone 2: scoring core and evaluation set, no LLM. The tools behind the four assignment questions are built first. Settles open points O7, O10, O11 and O12. → `docs/PLAN.md` section 13, `docs/ASSUMPTIONS.md`
- [q4] Milestone 3: the agent. → `docs/PLAN.md` section 13
- [q5] Milestone 4: API and chat page. → `docs/PLAN.md` section 13
- [q6] Milestone 5: results, documents, fresh-context review, final end-to-end check. → `docs/PLAN.md` section 13
- [q10] Deployment to a public URL, ask first. The assignment calls it preferred, so it stands apart from the bonuses. → `docs/PLAN.md` section 13
- [q8] Bonuses, ask first: score-change alert, voice. → `docs/PLAN.md` section 13

## Done / Dropped

- [q11] Session 02 transcript committed. Done 2026-11-24. Proof: commit `9d551f5`.
- [q2] Milestone 1: data. Done 2026-11-24. Proof: commits `5e67c19` to `d127f5b`; the checks' output is in session `02-data.txt`.
- [q9] Session 01 transcript committed. Done 2026-11-24. Proof: commit `4adbf00`.
- [q1] Milestone 0: scaffold and rules. Done 2026-11-24. Proof: commits `db31520`, `14817f0`, `e427e7b`; the three checks' output is in session `01-plan.txt`.
- [q7] Owner decision: how the score counts and weighs warnings. Done 2026-11-24. Proof: the entry "Count time under warning, with equal weights for the three warning hazards" in `docs/DECISIONS.md`. The band cut-offs it leaves open are part of q3.
