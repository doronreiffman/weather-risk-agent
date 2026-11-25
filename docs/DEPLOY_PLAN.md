# The public URL: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Grade: demo** (from the approved design): safe for one to two weeks of light use by the owner and a few reviewers; not production.

**Goal:** the chat page and its API on a public Koyeb URL behind a sign-in, with a daily cap on paid questions, while the local run stays exactly as it is.

**Architecture:** The server decides public mode from the address it listens on. In public mode it refuses to start without `WRA_ACCESS_CODE`, puts HTTP Basic authentication in front of every route but `/healthz`, and gives the agent a daily question limit. The agent drops its least recently used conversation past 200 in both modes. A Dockerfile builds the database into the image; Koyeb builds it from the public GitHub repository.

**Tech Stack:** Python 3.13, FastAPI, uvicorn, uv 0.11.0, pytest, Docker, Koyeb, GitHub (`gh`).

**Spec:** `docs/DEPLOY_DESIGN.md` (approved 2026-11-25). Read it with this plan.

**One refinement of the design, decided here:** the design puts the daily limit "in the API layer, so `wra ask`, `wra chat` and `wra eval` ... never meet it". Here the server hands the limit to the agent (`ClaudeAgent(..., admit=...)`), and only `wra serve` in public mode does so. Reason: `AgentReply.session_id` is a required `str` (`src/wra/agent/schemas.py:75`) and the page keeps the id an error reply carries (`src/wra/api/static/index.html`, the `else` branch after `unknown_conversation`), so a refusal on a new conversation must carry a real conversation id, which only the agent can make. The commands the design names still never meet the limit.

## Global Constraints

- Local mode (listening on `127.0.0.1`, `localhost` or `::1`) is unchanged: no sign-in, no daily limit. `uv run wra serve`, `uv run pytest -q`, `wra eval` and `scripts/e2e.sh` behave as today.
- Public mode is any other listen address. `WRA_ACCESS_CODE` missing or blank means the server refuses to start and says why.
- The door: HTTP Basic, username `analyst`, password the access code, compared in constant time; every route except `/healthz`.
- The daily limit: 100 questions a day (UTC), public mode only; the 101st gets status `error`, `error_code` `daily_limit`, HTTP 429, and no model call.
- Conversations held: at most 200; past that the least recently used is dropped; both modes.
- No test makes a paid call or a network call. No JavaScript packages; no agent framework.
- `.env` is never copied into an image or committed.
- Before every commit: `git status`, stage every file the message names, and `git diff --cached | grep -i -c -F "$(git config --global user.email | cut -d@ -f2)"` prints 0. A commit message claims only what was run on the tree being committed.
- `gh` runs only in the main session, one call per message, never batched with other tool calls. Subagents never push.
- A fact written in the README, a doc or a commit message is checked this session against its source, or marked UNVERIFIED for the owner.
- Paid calls (a question to the live site included) are the owner's to approve; report each one's cost.

## Review Focus

1. **The limit reached on a new conversation's first question.** The reply must carry a conversation id the agent holds, so the page's next question, after midnight UTC, continues it instead of meeting a 404. Test in Task 1.
2. **Malformed sign-in headers** (not `Basic`, bad base64, no colon, bytes that are not UTF-8) must get 401, never 500. Test in Task 2.
3. **An access code with a colon or a non-ASCII character** must work: split the decoded pair at the first colon, compare as UTF-8 bytes (`secrets.compare_digest` raises on non-ASCII `str`). Test in Task 2.
4. **`WRA_ACCESS_CODE` set to spaces** must count as missing, so the server refuses to start. Test in Task 2.
5. **Refusals that never reach the model** (busy, unknown conversation, a malformed request) must not use the daily count. Test in Task 1.

---

### Task 1: The agent's two limits

**Files:**
- Create: `src/wra/agent/limits.py`
- Modify: `src/wra/agent/schemas.py:19-20` (`ErrorCode`), `src/wra/agent/settings.py` (`AgentSettings`, `load_settings`), `config/agent.toml`, `src/wra/agent/loop.py:98-150` (`ClaudeAgent.__init__`, `answer`), `src/wra/api/app.py:29` (`ERROR_STATUS`) and its docstring
- Test: `tests/test_limits.py` (create), `tests/test_api.py:108-110` (`HTTP_STATUS`)

**Interfaces:**
- Produces: `utc_today() -> datetime.date`; `class DailyLimit(limit: int, today: Callable[[], date] = utc_today)` with `admit(self) -> bool` (thread-safe; the count starts again when `today()` changes); `ClaudeAgent(ctx, settings=None, client=None, admit: Callable[[], bool] | None = None)`; `AgentSettings.max_conversations: int` and `AgentSettings.daily_question_limit: int`; error code `"daily_limit"` sent as 429.

- [ ] **Step 1: Write the failing tests** in `tests/test_limits.py`, using `Scripted`, `final` from `test_agent_loop`, `REPO` from `conftest`, the module `ctx` fixture pattern of `tests/test_api.py`, and `dataclasses.replace(load_settings(REPO / "config" / "agent.toml"), max_conversations=2)` where a small cap is needed:
  - `test_the_daily_limit_admits_up_to_its_limit_then_refuses`: `DailyLimit(2, today=lambda: date(2026, 11, 25))`, three `admit()` calls give `[True, True, False]`.
  - `test_the_daily_limit_starts_again_on_a_new_utc_day`: limit 1; admit on day A is True, again False; `today` moved to day B, admit is True.
  - `test_a_question_over_the_limit_gets_daily_limit_and_reaches_no_model`: `ClaudeAgent(ctx, settings, Scripted(), admit=lambda: False).answer(None, "Which hubs?")` has `status == "error"`, `error_code == "daily_limit"`, `"midnight UTC" in reply.error`, `model.requests == []`, and `reply.session_id in agent.sessions` (Review Focus 1).
  - `test_refusals_before_answering_do_not_use_the_daily_count`: an `admit` that counts its calls; `answer("not-held", ...)` (unknown conversation) and a message on a conversation whose `busy` lock is held both leave the count at 0 (Review Focus 5).
  - `test_the_least_recently_used_conversation_is_dropped_past_the_cap`: cap 2; open conversations A, B; send a follow-up on A; open C; then `B not in agent.sessions`, `A in agent.sessions`, and a message on B gets `error_code == "unknown_conversation"`.
  - In `tests/test_api.py`, add `"daily_limit": 429` to `HTTP_STATUS`; the existing parametrized test then checks the 429.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest -q tests/test_limits.py tests/test_api.py`
Expected: failures on the missing module, the missing `admit` argument, and `daily_limit` not being an `ErrorCode`.

- [ ] **Step 3: Implement**
  - `config/agent.toml`: `max_conversations = 200  # held in memory; past it the least recently used is dropped (docs/DEPLOY_DESIGN.md 5.4)` and `daily_question_limit = 100  # public mode only (docs/DEPLOY_DESIGN.md 5.3)`.
  - `settings.py`: the two fields, read as `int(raw[...])`.
  - `limits.py`: `DailyLimit` with a `threading.Lock`, the current day and its count.
  - `schemas.py`: append `"daily_limit"` to `ErrorCode`, and to its comment: sent as 429.
  - `loop.py`: `self.sessions` becomes an `OrderedDict`; a found session is moved to the end; a new one is added at the end, then the oldest are popped while `len > settings.max_conversations`; all of this inside `_sessions_lock`. After the `busy` lock is acquired and before `_answer`, `if self.admit and not self.admit(): return self._error_reply(session.id, DAILY_LIMIT, "daily_limit")`, with `busy` still released by the existing `finally`. `DAILY_LIMIT = "Today's question limit for this demo is used up, so this question was not sent. It starts again at midnight UTC."`
  - `app.py`: `ERROR_STATUS` gains `"daily_limit": 429`; the docstring's HTTP paragraph names it.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest -q`
Expected: all pass (367 before this task, plus the new ones).

- [ ] **Step 5: Commit** `src/wra/agent/limits.py src/wra/agent/schemas.py src/wra/agent/settings.py src/wra/agent/loop.py src/wra/api/app.py config/agent.toml tests/test_limits.py tests/test_api.py` with a message naming the two limits and the test count.

### Task 2: Public mode and the door

**Files:**
- Create: `src/wra/api/public.py`
- Modify: `src/wra/api/app.py:54` (`create_app`), `src/wra/cli.py:72-75` (`--host` help) and `:198-210` (`_serve`)
- Test: `tests/test_public.py` (create), `tests/test_cli.py:138-156`

**Interfaces:**
- Consumes: `DailyLimit`, `ClaudeAgent(..., admit=...)`, `AgentSettings.daily_question_limit` (Task 1).
- Produces: `USERNAME = "analyst"`; `is_public(host: str) -> bool` (False only for `127.0.0.1`, `localhost`, `::1`); `access_code_from_env() -> str | None` (`WRA_ACCESS_CODE` stripped; empty means None); `credentials_ok(header: str | None, access_code: str) -> bool`; `add_door(app: FastAPI, access_code: str) -> None`; `create_app(agent, ctx, access_code: str | None = None)`.

- [ ] **Step 1: Write the failing tests** in `tests/test_public.py` (code `"pa:ss-ü"` where not stated, `TestClient(..., auth=("analyst", code))` for the right credentials):
  - `test_the_door_refuses_without_or_with_wrong_credentials`: GET `/`, `/api/hubs`, `/docs`, `/openapi.json` with no auth, with `("analyst", "wrong")` and with `("admin", code)` give 401 and a `WWW-Authenticate` header starting `Basic`; POST `/api/chat` gives 401 and the scripted model's `requests == []`.
  - `test_the_door_lets_the_right_credentials_through`: `/` and `/api/hubs` give 200; a question on `Scripted(tool("rank_hubs", WINTER_MIDWEST), final())` is answered (Review Focus 3, the code has a colon and a non-ASCII letter).
  - `test_healthz_needs_no_sign_in`: 200 and `{"status": "ok", "hubs": 12}` with no auth.
  - `test_malformed_sign_in_headers_get_401`: `Authorization` set to `"Bearer x"`, `"Basic !!!"`, `"Basic " + b64("nocolon")`, `"Basic " + b64(b"\xff\xfe")` each give 401 (Review Focus 2).
  - `test_no_door_without_an_access_code`: `create_app(agent, ctx)` serves `/` with 200 and no auth.
  - `test_which_addresses_are_public`: `is_public` is False for `127.0.0.1`, `localhost`, `::1` and True for `0.0.0.0`, `192.168.1.5`.
  - `test_a_blank_access_code_counts_as_missing`: with `WRA_ACCESS_CODE` unset, `""` and `"   "`, `access_code_from_env()` is None; `" abc "` gives `"abc"` (Review Focus 4).
  - In `tests/test_cli.py`, rework `test_serve_listens_on_this_machine_only_unless_told_otherwise`: record `ClaudeAgent`'s keyword arguments by monkeypatching `wra.agent.loop.ClaudeAgent`; local `serve` has `admit` None and `/` gives 200 with no auth; with `WRA_ACCESS_CODE=test-code`, `serve --host 0.0.0.0 --port 8123` returns 0, `admit` is not None, `/` gives 401, `/healthz` gives 200. Add `test_serve_refuses_to_go_public_without_an_access_code`: with the variable unset, `main(["serve", "--host", "0.0.0.0"]) == 2`, `uvicorn.run` was not called, and stderr names `WRA_ACCESS_CODE`.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest -q tests/test_public.py tests/test_cli.py`
Expected: failures on the missing module and on the old serve behaviour.

- [ ] **Step 3: Implement**
  - `public.py`: `credentials_ok` parses `Basic <base64>`, decodes strictly to UTF-8 (any error gives False), splits at the first colon, and compares username and code as UTF-8 bytes with `secrets.compare_digest`. `add_door` registers an `@app.middleware("http")` that passes `/healthz` and answers anything else without good credentials with `JSONResponse({"detail": "Sign in with the username analyst and the access code."}, status_code=401, headers={"WWW-Authenticate": 'Basic realm="Weather Risk Agent", charset="UTF-8"'})`.
  - `app.py`: `create_app` calls `add_door(app, access_code)` when `access_code` is given.
  - `cli.py` `_serve`: when `is_public(host)`, read the code; without one, print to stderr `error: listening on {host} makes the server public, and WRA_ACCESS_CODE is not set. Set it, or listen on 127.0.0.1.` and return 2 before building anything. Public mode builds `ClaudeAgent(ctx, settings, admit=DailyLimit(settings.daily_question_limit).admit)` and `create_app(agent, ctx, access_code=code)`, and its start-up line adds `Public mode: sign-in required, at most {n} questions a day.` Local mode stays as today. The `--host` help says any other address is public mode and needs `WRA_ACCESS_CODE`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit** `src/wra/api/public.py src/wra/api/app.py src/wra/cli.py tests/test_public.py tests/test_cli.py`.

### Task 3: The image

**Files:**
- Create: `Dockerfile`, `.dockerignore`
- Test: `tests/test_container.py` (create)

**Interfaces:**
- Consumes: public mode from Task 2 (`wra serve --host 0.0.0.0` needs `WRA_ACCESS_CODE`).
- Produces: an image that listens on `${PORT:-8000}` with the database already built.

- [ ] **Step 1: Write the failing tests** in `tests/test_container.py`, reading the two files as text:
  - `test_the_image_never_gets_the_secrets_or_the_transcripts`: `.dockerignore` lines include `.env`, `.env.*`, `.venv`, `evals/runs`, `docs/ai-session`, `.git`.
  - `test_the_image_builds_the_database_and_serves_publicly`: the Dockerfile has a `RUN` line containing `wra ingest`, and its `CMD` contains `--host 0.0.0.0` and `${PORT:-8000}`.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest -q tests/test_container.py`
Expected: FAIL, the files do not exist.

- [ ] **Step 3: Write the two files.** `python:3.13-slim`; uv copied from `ghcr.io/astral-sh/uv:0.11.0` (the local version; the nearest published tag if that one is missing); `UV_COMPILE_BYTECODE=1`; dependencies synced from `pyproject.toml` and `uv.lock` first (`uv sync --frozen --no-dev --no-install-project`), then the project, then `.venv/bin/wra ingest`; `CMD ["sh", "-c", "exec /app/.venv/bin/wra serve --host 0.0.0.0 --port ${PORT:-8000}"]`, calling the venv's script directly so start-up skips uv. `WORKDIR /app`, which is also `paths.root()` since it defaults to the working folder.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Build and try the image locally (Docker 29.2.1 runs here; no API key goes in, so no paid call)**
  - `docker build -t wra-demo .` succeeds.
  - `docker run --rm wra-demo sh -c 'ls -a /app'` lists no `.env`.
  - `docker run --rm -e PORT=8000 wra-demo` without `WRA_ACCESS_CODE` exits with status 2 and the error line.
  - `docker run --rm -d --cpus=0.1 --memory=512m -e WRA_ACCESS_CODE=local-test -p 8780:8000 wra-demo`, then time the first `200` from `curl http://127.0.0.1:8780/healthz`, three runs. Report the figure to the owner: it is the closest stand-in for Koyeb's free instance (0.1 vCPU, 512 MB) before deploying.
  - `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8780/` gives 401; with `-u analyst:local-test` gives 200. Stop the container.

- [ ] **Step 6: Commit** `Dockerfile .dockerignore tests/test_container.py`, the message giving the measured start-up time at 0.1 CPU.

### Task 4: Documents and the rule change

**Files:** `README.md`, `docs/ARCHITECTURE.md` ("The API and the chat page", "How failures surface"), `docs/DECISIONS.md` (append), `docs/PLAN.md` (`## Deviations`, append), `docs/ASSUMPTIONS.md` (O1, and a deployment section), `CLAUDE.md` (rule 7), `.claude/OPEN_ISSUES.md`, `.claude/QUEUE.md`.

- [ ] **Step 1: Write them.**
  - README: "Public mode" under running it (what changes when `--host` is not local; `WRA_ACCESS_CODE`; the two limits) and "Interview day", the runbook from design 5.8. The live URL and the measured wait come in Task 6.
  - ARCHITECTURE: public mode and the door; the two limits; 401 (the door, no reply body) and 429 (`daily_limit`) in the failures table.
  - DECISIONS: `## 2026-11-25 — Public mode is decided by the listen address and fails closed`, with Decision, Why (the Koyeb choice and the alternatives from design section 4; the browser sign-in box over a code field; the limit given to the agent, and why), Context (the design and plan paths, the files of Tasks 1 to 3).
  - PLAN Deviations: deployment as built, pointing to the design.
  - ASSUMPTIONS: O1 extended to a public repository (owner, 2026-11-25); the in-memory count starting again after each sleep, with the workspace limit as the ceiling.
  - CLAUDE.md rule 7: secrets live only in the git-ignored `.env`, plus the demo key and access code in the host's secret settings (owner, 2026-11-25).

- [ ] **Step 2: Check them.** Every figure and fact against its source (design, code, test output). Then the scan, counts only: `git diff -U0 HEAD -- . | grep -i -c -F -e "$(git config --global user.email | cut -d@ -f2)"` prints 0, and the same for the names list kept outside the repository (Task 5, step 1).

- [ ] **Step 3: Run the tests.** `uv run pytest -q`: all pass. `scripts/e2e.sh` (free part): PASSED.

- [ ] **Step 4: Commit** the files listed above.

**Then, before Task 5: the whole-branch review** by a fresh Fable subagent (global rule: each build's whole-branch review), over the diff from `0d0cafb` to the last commit, against `docs/DEPLOY_DESIGN.md` and this plan, reporting only gaps that affect correctness, safety of the public site or the design's goals. Fix what it finds; its findings are checked against the code before any is acted on.

### Task 5: Going public on GitHub (main session, on the owner's go)

- [ ] **Step 1: The final scan.** Over every commit (`git log -p --all`): the work email domain, the names from the owner's global instructions, any in the owner's optional terms file (`grep -i -c -F -f <file>`), `sk-ant-` followed by key characters, and claude.ai session links. Commands print counts only. Every session transcript committed so far is included; the session 06 transcript's one work project name is reworded before it is committed. Any hit stops here for the owner.
- [ ] **Step 2: The owner's go** for the push, shown the scan's counts.
- [ ] **Step 3: Switch `gh` to the personal account** (its own message): `gh auth switch --hostname github.com --user doronreiffman`. The flags in steps 3 and 4 are written from memory: read `gh auth switch --help` and `gh repo create --help` first.
- [ ] **Step 4: Create and push** (its own message): `gh repo create doronreiffman/weather-risk-agent --public --source . --remote origin --push`. Then `git ls-remote origin main` shows the local `main`'s commit.
- [ ] **Step 5: Switch `gh` back** to the account that was active before (its own message). Every later push repeats steps 3 and 5 around it.

### Task 6: Deploy and check (the owner clicks; the main session gives the steps and checks)

- [ ] **Step 1: The demo key (owner).** In the Anthropic Console: a new workspace for the demo; its monthly spending limit (5 USD proposed); a key scoped to it. Kept out of every file.
- [ ] **Step 2: The service (owner).** On Koyeb: an account (card, $29 hold cancelled at once); connect the personal GitHub account; a web service from `weather-risk-agent`, built from the Dockerfile, on the free instance, port 8000, health check on `/healthz`; secrets `ANTHROPIC_API_KEY` (the demo key) and `WRA_ACCESS_CODE` (a code the owner picks). Field names as Koyeb's form shows them; Claude does not drive the browser.
- [ ] **Step 3: Free checks (main session).** `curl -s <URL>/healthz` gives `{"status":"ok","hubs":12}`; `curl -s -o /dev/null -w '%{http_code}' <URL>/` gives 401.
- [ ] **Step 4: The owner's checks in the browser** (one paid question, under a cent): the sign-in box appears; a wrong code is refused; README page-check steps 1 and 3 pass (steps 2 and 4 stop the server, so they stay local-only).
- [ ] **Step 5: The wake-up wait.** After at least an hour with no traffic: `curl -s -o /dev/null -w '%{http_code} %{time_total}\n' <URL>/healthz`, on two separate idle spells. Report both to the owner with the Task 3 figure, for the host decision in design goal 2.
- [ ] **Step 6: Record it.** README "Public demo": the URL, the code sent separately, the limits, the measured wait. `.claude/QUEUE.md`: q10 to Done with its proof; the host re-evaluation as its own line if the owner wants one. Commit, then push with Task 5's steps 3 to 5.

## Deviations

(Changes reality forces during the build are appended here.)

- *Setup.* The build ran on a branch, `public-url`, in the main checkout rather than a separate worktree: one task at a time, and the git-ignored database and `.env` live in this checkout.
- *Task 3, the tests.* The plan's second container test, reading the Dockerfile's text, was dropped: it would only prove the file says what it says. The image is checked by building and running it (step 5). The `.dockerignore` test stays, since removing `.env` from that list is a security bug.
- *Task 3, the measured start.* At Koyeb's free size (`--cpus=0.1 --memory=512m`) the image took 41.7 to 43.7 s to its first healthy reply, against the design's estimate of 15 to 30 s; 2.8 s at one CPU. Importing Anthropic's SDK is 1.12 of the 2.10 processor seconds at one CPU. Reported to the owner before Task 5; no change to the plan.
