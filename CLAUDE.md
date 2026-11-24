# Weather Risk Intelligence Agent

A take-home for a Forward Deployed Engineer role. The customer is a logistics company's analysts deciding which hubs get resilience investment this year. Everything built here serves that decision: a ranking they can defend, an explanation they can repeat to their boss, and honesty about what the data cannot tell them.

Python with `uv` and `pytest`.

## Where things are

- `docs/PLAN.md` is the approved spec. Read it at the start of every session: its milestone list says what is next and which check ends it. When reality forces a change from it, append the change to its `## Deviations` section.
- `.claude/QUEUE.md` is the ordered work queue.
- `docs/DECISIONS.md` is the decision log. Read it before an architectural choice and add a short entry when one is made.
- `docs/ASSUMPTIONS.md` is the live list of assumptions and open points. Update it in the same commit that changes one.

## Rules for the build

1. **Numbers come from code.** The risk score is deterministic and unit-tested with no LLM, with its weights in a config file. The LLM understands the question, calls our tools and explains the results. Every number in an answer comes from a tool result.
2. **LLM output is validated in code** against a JSON schema (Pydantic). Invalid output gets one repair attempt, then a clear error.
3. **Evidence, not claims.** A milestone is done when its check passes: paste the command and its output.
4. **The evaluation set exists before the agent does:** 10 to 15 questions with automatic checks, one command that runs them and prints a score.
5. **Say what we don't know.** The agent's answers state the data period, the sources and the confidence.
6. **Small commits with clear messages.** A commit message claims only what was actually run.
7. **Secrets live only in the git-ignored `.env`.** Work from `.env.example`. `.env` itself stays unread and unprinted; `.claude/settings.json` denies it.
8. **Ask rather than guess, and push back** when there is a better approach.
9. **Match the model to the task** and say which was picked and why: Fable for open design questions and the final whole-diff review, Opus for implementation and per-milestone review, Sonnet for small, fully specified tasks. The main session's model and effort level are the owner's to switch, so say when they should change.
10. **Bonuses** (deployment, score-change alert, voice, in that order) start only after the final end-to-end check passes, and only after asking.
11. **Measure before proposing.** Before proposing a number, check whether data already in hand can measure it. A number that confirms the expected answer gets checked hardest.

## Sessions are a deliverable

At the end of each milestone, remind the owner to run `/export` into `docs/ai-session/` (numbered `01-plan.txt`, `02-...`) before `/clear`, and add one line for that session to `docs/ai-session/README.md`. `docs/ai-session/` stays tracked by git.
