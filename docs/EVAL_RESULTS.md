# Evaluation results

Milestone 5, run on 24 November 2026 (UTC), on commits `4e4ae6a` to `27c5b6d` (the tree each run used is named below). The agent ships on **Claude Haiku 5.5**, the owner's choice from the comparison in this document.

## What was run

Fourteen cases (plan section 10.1): the four assignment questions, two follow-ups, a what-if and the return from it, an overall top three, the method, three out-of-scope questions and a year outside the data. Each case ran three times. Every check is code, never a model (plan section 10.2): the expected status, the right tool called with the key arguments, the hub order against the scoring code, the tables against a fresh run of the tool, and required or forbidden words. The clock is pinned to 2026-11-24, so "last year" is 2025.

The target (plan section 10.3): the four assignment questions pass in every repetition, and at least 90% of all case runs pass.

Every run below is kept under `evals/runs/` and committed, so each figure here can be checked against its record.

## The model comparison

All three models ran unchanged: the same prompt, tools and checks, at effort `medium`.

| Model | Run | Case runs passed | Answers refused | Answers repaired | Target | Cost | Per answer | Median answer time |
|---|---|---|---|---|---|---|---|---|
| Opus 5.5 | `20261124T220322Z-claude` | 42 of 42 | 0 of 57 | 1 | met | 1.14 USD | 2.0 cents | 5.0 s |
| Sonnet 5.5 | `20261124T220803Z-claude` | 36 of 42 (38 after the grader fixes) | 4 of 57 | 1 | not met | 0.66 USD | 1.2 cents | |
| Haiku 5.5 | `20261124T221217Z-claude` | 41 of 42 | 2 of 57 | 2 | met | 0.04 USD | 0.075 cents | |
| Haiku 5.5, band check fixed | `20261124T223759Z-claude` | 41 of 42 | 0 of 57 | 2 | met | 0.04 USD | 0.074 cents | 4.5 s |

The first three runs used the agent as of commit `4e4ae6a`; the last used `7197faa`. A refused answer is one that ended in a plain error instead of an answer: the checks rejected it twice, or the model used its six calls without answering. The analyst never sees an unchecked answer. Costs are at list price, from the API's own token counts.

**The owner chose Haiku 5.5.** The plan's rule (section 9) was the cheapest model whose score equals the best; by that rule Opus wins by one case run. Haiku costs about one twenty-seventh as much per answer, refuses none, and its one miss is a right answer written in words (below). Every later evaluation also costs cents instead of about a dollar.

## The final end-to-end run

`scripts/e2e.sh --paid` on commit `27c5b6d`, which carries the fixes from the final review (`1b455ab`) and each hazard's order as a checked field of the answer (`d63c0ba`); the commits after `d63c0ba` change only documents. It ran in a fresh clone with no `.env` of its own. The database was built offline and `uv run pytest -q` passed 360 tests in the clone. Through the HTTP API, the four assignment questions, the follow-up and the Seattle question all passed (6 of 6, about 0.01 USD); the follow-up named Columbus and showed the Midwest winter table. The evaluation then ran on Haiku 5.5: **42 of 42 case runs passed, no answer refused, none repaired, target met**, 0.043 USD, all 57 answers served by Haiku 5.5 (run `20261124T234915Z-claude`). In all three repetitions the Miami and Houston answer stated each hazard's order in the checked field, and the order matched the result: Miami leads on hurricanes, Houston on floods. The four assignment answers below are from this run.

An earlier run on `1b455ab`, before the hazard order field, also passed 42 of 42 (run `20261124T232102Z-claude`, 0.039 USD).

## What failed, and why

**Haiku's two refusals were a bug in our band check.** Both came on "What if a hurricane counted double?". Haiku ran the what-if, labelled it, named Miami Very high (true in the what-if) and cited the official ranking as well. The check kept one band per hub, the last one cited, so it compared Very high with the official Moderate and refused a right answer twice. It now accepts any band a cited result gives the hub (`src/wra/agent/checks.py`, `_cited_bands`). With the fix, Haiku refused nothing.

**Haiku's remaining miss** is case 10, repetition 1: the method answer wrote the weights as "one day" and "five days". The grader requires figures, because the number check reads digits only, so a weight in words would go unchecked (owner, milestone 2). The answer was otherwise right.

**Sonnet's two doubtful grades were grader bugs or strictness, now fixed with the owner's agreement.** Its earthquake answer said "earthquakes" and failed a whole-word match for "earthquake"; the grader now allows a final s. Its answer to "Which of the two is worse overall?" said neither hub is clearly worse (Houston 1.96, Miami 1.85, within the year-to-year swings) and gave no order; that now passes when the verdict says so. Re-grading the saved answers changed exactly those two case runs. The three fixes are in `docs/ASSUMPTIONS.md`, milestone 5 section.

**Sonnet's real problem: it repeats tool calls until it runs out.** In 4 of its 57 answers it made six model calls without answering, the limit per message; one was the Dallas assignment question. It repeated an identical call in 10 answers; Opus and Haiku never did.

## Diagnosing Sonnet

| Test, on the five question types where Sonnet repeated calls, three times each | Run | Case runs with a refusal | Tool calls | Identical repeats | Cost |
|---|---|---|---|---|---|
| Opus, effort medium (from the comparison run) | `20261124T220322Z-claude` | 0 of 15 | 18 | 0 | 0.39 USD |
| Sonnet, effort medium (from the comparison run) | `20261124T220803Z-claude` | 4 of 15 | 50 | 19 | 0.32 USD |
| Sonnet, effort high | `20261124T223122Z-claude` | 1 of 15 | 45 | 21 | 0.35 USD |
| Sonnet, medium, a prompt line: "never call a tool again with arguments you have already used; cite the earlier result_id" | `20261124T224015Z-claude` | 3 of 15 | | 19 | 0.32 USD |
| Sonnet, medium, a loop guard answering an identical call with a note naming the earlier result | `20261124T224258Z-claude` | 3 of 15 | | 16 | 0.29 USD |

The three Sonnet tests ran on `7197faa`; the prompt line and the guard were uncommitted changes on top of it, each run alone.

- **Ruled out:** our code treating Sonnet differently (the same request, and its own turn sent back unchanged), a substitute model (all 57 answers served by Sonnet), and effort as the root cause (high cut the refusals, not the repeats).
- **Seen in a replay with thinking shown:** on the Dallas question, the two identical calls came with no thinking at all, then Sonnet answered on its fourth call. With the guard on, it asked for the same overall ranking five times in a row, each time told the result was unchanged.
- **Not tested:** how Sonnet handles a tool loop when every reply must match the answer schema. Testing it means splitting the loop into tool calls without the schema and one final structured call (the plan's milestone 3 fallback), a change to the agent's design.
- **Why the owner stopped there:** on these questions Sonnet's extra calls bring its cost close to Opus's (0.29 to 0.35 USD against 0.39), while Haiku costs about 96% less. The prompt line and the guard were removed; neither is in the code.

The diagnosis cost 1.02 USD, including a replay of two questions with thinking shown (0.06 USD, not a run record).

## Verdict length

The plan asks for at most four short sentences. On Opus, 6 of 57 verdicts ran to five, all at five; part of the length is the plain-word definitions added before milestone 5. On Haiku, none ran past four (2 sentences in 16 verdicts, 3 in 36, 4 in 5). The count splits sentences at end punctuation, including one closed by bold; it was checked by hand on 14 Opus verdicts and 8 Haiku verdicts. Accepted by the owner (`docs/ASSUMPTIONS.md`, O14).

## Limits

- **Fourteen cases is a regression gate, not a fine instrument.** At 42 case runs and a 90% pass rate, the usual 95% margin is about plus or minus 9 points, and repeats of the same question are not independent, so the real margin is wider.
- **The number check confirms that each figure is in a cited result, not which hub or hazard it belongs to.** A right figure for the wrong hub or hazard passes it: "Houston leads on hurricanes at 1.52" would pass, since 1.52 is in the result as Miami's figure (final review, run offline on a scripted model). A wrong small whole number can match a rank or a count, and a claim in words goes unchecked. No saved answer swapped figures. The answer now states each hazard's order in a field code checks against the cited result, the Miami and Houston case grades that field, and a code-written note under the comparison table says which hub leads each hazard. The tables beside each verdict always show the computed figures.
- **A claim in words can be false.** In an earlier run (`20261124T223759Z-claude`), the Dallas answer said winter drives its risk "mainly under winter storm, ice storm and blizzard warnings". That is wrong: Dallas had 6 Winter Storm Warnings, 1 Ice Storm Warning and no Blizzard Warning in 2016 to 2025. No tool result splits winter by warning type; the model took the list from the score's description, which names every type the score counts. The system prompt now tells the model to name warning types only when a result lists them for that hub (final review); none of the final run's three Dallas answers names one.
- **Prose quality is not graded.** The four assignment answers follow in full for a person to read.

## The four assignment answers, as the shipped model gave them

From the final end-to-end run, `20261124T234915Z-claude`, repetition 1. The page shows each with the cited tables, their notes, and the data, period and confidence lines.

### 1. Which hubs in the Midwest are most exposed to winter disruption?

**Minneapolis (MSP)** is clearly the most exposed Midwest hub to winter disruption, with about 2.71 disruption days a year, and its lead over Kansas City is clear of year-to-year swings. **Kansas City (MCI)**, **Chicago (ORD)** and **Indianapolis (IND)** follow, but their gaps are within year-to-year swings, so their relative order is not settled. **Columbus (CMH)** is the least exposed at 0.66 days a year.

- Confidence is low: the data is complete, but three of the four gaps between hubs are smaller than normal year-to-year swings, so only the top spot is firm.
- The score counts only time under a winter warning, while winter road effects often outlast the warning, so it may understate winter's impact relative to floods and storms.

Confidence: low. Table: Winter weather exposure, Midwest hubs: expected disruption days a year.

### 2. Compare Miami and Houston in terms of hurricane and flood exposure.

**Miami is the more exposed hub for hurricanes**, at 1.52 expected disruption days a year against Houston's 0.92. **Houston is the more exposed hub for flooding**, at 0.47 days against Miami's 0.21, and that gap is large enough to be treated as settled. Both hurricane figures are scored as expected disruption days a year, so they are not a count of days with a storm.

- The hurricane gap cannot be tested against year-to-year swings, because FEMA gives one long-run hurricane figure for 1851 to 2024 with no yearly values, so the Miami-over-Houston hurricane order is less certain than the flood order.
- Both hubs' hurricane-warning days are close to each other (Miami 1.58, Houston 1.29 a year, not scored), so the scored hurricane gap depends mostly on FEMA's long-run frequency, and this comparison covers weather at the airport locations only, not site-level flood risk.

Confidence: medium. Table: Miami and Houston: expected disruption days a year, compared. Its hazard order field gave Miami first on hurricanes and Houston first on floods, checked in code against the cited result.

### 3. What percentage of days in Denver last year had snowfall?

In 2025, **7.1%** of observed days in Denver had measurable snowfall, meaning 0.1 inch or more fell that day. A further 19 days had only a trace (snow fell but too little to measure), and those are not counted in the 7.1%.

- The figure is for Denver's airport weather station (Denver International Airport), not the distribution hub site itself, and covers 2025 only; one day was missing and was left out of the percentage.

Confidence: high. Table: Denver (DEN): days with measurable snowfall, 2025.

### 4. Why is the Dallas hub's weather disruption risk high?

Dallas scores **2.02 expected disruption days a year**, which the tool places in the **High** band (2 or more days) and ranks 6th of 12 hubs. Winter weather drives about 47% of that figure, flooding about 31%, and severe storms about 19%; hurricanes add only about 3%. The score sits just above the High cutoff, and the hubs directly above and below it (Chicago and Houston) are very close, so Dallas is best read as mid-to-high exposure rather than an extreme outlier.

- Confidence is low: the data holds all the records needed, but the gaps that exist fall within the hub's normal year-to-year swings, so the exact placement could shift with more data.
- The score counts only time under a National Weather Service warning (an official alert that severe weather is expected or occurring over the hub). Winter's effect on freight roads lasts longer than its warning, so the score may understate winter exposure.
- This measures weather at the Dallas airport station only; it does not show site-level flood risk or how much the hub matters to the business.

Confidence: low. Table: Dallas (DAL): 2.02 expected disruption days a year, High, 6th of 12.
