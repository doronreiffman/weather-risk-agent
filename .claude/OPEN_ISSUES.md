# Open issues

The living list of what is open now: blockers, deferred findings, "fix someday". Each entry holds its current state; it is replaced when the state changes and deleted when resolved (git keeps the history). Open facts and assumptions about the data stay in `docs/ASSUMPTIONS.md`.

## The chat page

- **The page's own logic has no automated test** (handoff review of session 04). Covered: the bold renderer runs in Node in `tests/test_api.py` (skipped when Node is missing); the owner tried the server-restart path by hand at the milestone 4 page check and it worked. Not covered by any test: the "New conversation" button, the question kept or put back in the box, the reset after a 404. Accepted by the owner 2026-11-24: a written check by hand, README "Checking the page by hand before a demo" (four steps, one paid question); a Node test against a hand-written stand-in for the page was offered and not chosen. Last runs: all four steps passed locally, owner, 2026-11-25, on `4bc1367`; on the public site, owner, 2026-11-25, sign-in (a wrong code refused), step 1 and step 3 passed (steps 2 and 4 stop the server, so they are local-only). Next: rerun after any change to the page. Refs: `src/wra/api/static/index.html`, `tests/test_api.py`, `README.md`.

## The public site

- **Small findings left from the whole-branch review** (Fable, 2026-11-25; the owner chose to fix only the sign-in hardening, `88342f0`). Each is safe as it stands: a code in `.env` is ignored, since `WRA_ACCESS_CODE` is read before `.env` loads (the server refuses to start; the message and README could say "environment, not `.env`"); `/docs` lists 404, 409, 502 and 500 but not 429; `create_app(access_code="")` builds an open app, guarded only by `_serve`; `.dockerignore`'s `.env` patterns match the root only (no nested `.env` exists); each refused first question past the daily limit holds an empty conversation, which counts toward the 200; public mode starts healthy without `ANTHROPIC_API_KEY`, then every question is a 502; only the modules `wra ingest` imports are byte-compiled in the image (no measurable effect); leftover wording in `wra serve`'s description and README's "404 ... (after a restart)". Next: the owner names any to fix. Refs: `src/wra/cli.py` `_serve`, `src/wra/api/app.py`, `src/wra/agent/loop.py`, `Dockerfile`.

## The agent and its checks

- **Sonnet 5.5 repeats identical tool calls; cause not found** (not shipped). In 10 of 57 answers, up to the six-call limit; effort high, a prompt line and a loop guard each left it in place (all removed). Untested: the answer schema applied only to a final call. Matters only if Sonnet is chosen again. Refs: `docs/EVAL_RESULTS.md`, "Diagnosing Sonnet"; `docs/ASSUMPTIONS.md` milestone 5, point 5.
- **Prose can contradict the answer's own structured claims** (`hubs_ranked`, `hazard_orders`); code checks the claims, not the prose, and the grounding check reads digits only. Accepted (decision log, 2026-11-25); the code-written tables and lead note keep the true figures on the page. Refs: `docs/EVAL_RESULTS.md`, "Limits".

