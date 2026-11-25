# Open issues

The living list of what is open now: blockers, deferred findings, "fix someday". Each entry holds its current state; it is replaced when the state changes and deleted when resolved (git keeps the history). Open facts and assumptions about the data stay in `docs/ASSUMPTIONS.md`.

## The chat page

- **The page's own logic has no automated test** (handoff review of session 04). Covered: the bold renderer runs in Node in `tests/test_api.py` (skipped when Node is missing); the owner tried the server-restart path by hand at the milestone 4 page check and it worked. Not covered by any test: the "New conversation" button, the question kept or put back in the box, the reset after a 404. Accepted by the owner 2026-11-24: a written check by hand, README "Checking the page by hand before a demo" (four steps, one paid question); a Node test against a hand-written stand-in for the page was offered and not chosen. Last run: all four steps passed, owner, 2026-11-25, on `4bc1367`. Next: rerun it after any change to the page and on the public URL once it is up (q10). Refs: `src/wra/api/static/index.html`, `tests/test_api.py`, `README.md`.

## The public site

- **A start after an idle hour is slow on Koyeb's free instance** (0.1 of a CPU). Measured locally in the image at that size: about 42 s to the first healthy reply (41.7 to 43.7 s, three runs); about half the start-up is importing Anthropic's SDK. Owner 2026-11-25: stay on Koyeb free for now and re-evaluate. Next: measure the wait on Koyeb after the deploy (`docs/DEPLOY_PLAN.md` Task 6, step 5); the owner then decides; Render paid is the ready fallback. Refs: `docs/ASSUMPTIONS.md`, public URL section, point 2.

## The agent and its checks

- **Sonnet 5.5 repeats identical tool calls; cause not found** (not shipped). In 10 of 57 answers, up to the six-call limit; effort high, a prompt line and a loop guard each left it in place (all removed). Untested: the answer schema applied only to a final call. Matters only if Sonnet is chosen again. Refs: `docs/EVAL_RESULTS.md`, "Diagnosing Sonnet"; `docs/ASSUMPTIONS.md` milestone 5, point 5.
- **Prose can contradict the answer's own structured claims** (`hubs_ranked`, `hazard_orders`); code checks the claims, not the prose, and the grounding check reads digits only. Accepted (decision log, 2026-11-25); the code-written tables and lead note keep the true figures on the page. Refs: `docs/EVAL_RESULTS.md`, "Limits".

