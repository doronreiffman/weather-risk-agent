# Open issues

The living list of what is open now: blockers, deferred findings, "fix someday". Each entry holds its current state; it is replaced when the state changes and deleted when resolved (git keeps the history). Open facts and assumptions about the data stay in `docs/ASSUMPTIONS.md`.

## The chat page

- **The page's own logic has no automated test** (handoff review of session 04). Covered: the bold renderer runs in Node in `tests/test_api.py` (skipped when Node is missing); the owner tried the server-restart path by hand at the milestone 4 page check and it worked. Not covered by any test: the "New conversation" button, the question kept or put back in the box, the reset after a 404. A browser-level test would need a JavaScript package, which the project excludes. Next: the owner settles the approach in the next session (queue q16). Refs: `src/wra/api/static/index.html`, `tests/test_api.py`.
