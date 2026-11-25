# The public URL: design

**Grade: demo.** Safe for one to two weeks of light use by the owner and a few reviewers. Not production: no user accounts, no monitoring, one instance.

Status: **approved by the owner on 2026-11-25; the host changed to Render the same day, after the build (section 9).** Queue item q10. Facts marked "read 2026-11-25" were checked that day on the source named; anything else is marked. A fresh reviewer read it as its builder; its questions and the owner's answers are folded in (section 8).

## 1. Why, and for whom

The assignment: "You should be able to run the agent live during the follow-up interview. Deploying it to a URL is preferred, but not mandatory." The owner: the key is being able to run it on the day of the interview.

Two audiences:

- **In the story,** the logistics company's analysts open the page daily. The sign-in step stands in for the company's own sign-on.
- **In reality,** the owner shows it in the interview, and the people reviewing the assignment may try it on their own beforehand, probably within one to two weeks. The owner will not be there to restart or explain it.

## 2. Goals, non-goals, anti-goals

Goals, most important first:

1. **Interview day works.** The owner can show the agent live from the public URL, or, if that fails, from the laptop within about a minute.
2. **A reviewer can use it alone.** With the link and the access code, the chat page answers. After an idle hour the first page waits while the instance wakes, likely 15 to 30 seconds (section 3). That wait is measured on the real URL after the first deploy and stated in the README, and the owner re-evaluates the host with the measured figure (owner, 2026-11-25).
3. **Spend is bounded.** No one without the code reaches the model; with the code, a burst of questions has a ceiling; a hard monthly ceiling sits at Anthropic.
4. **The local run is unchanged.** `uv run wra serve`, the tests, `wra eval` and `scripts/e2e.sh` behave exactly as today, with no sign-in.

Non-goals: user accounts, conversations that survive a restart, a custom domain, more than one instance, monitoring or alerts, a CI pipeline.

Anti-goals (a failure even if everything else works):

- A reviewer's first impression is an error page or a long wait.
- The public site runs without the guard because a setting was missing.
- The API key, the access code, or text identifying the owner's employer ends up in the public repository or its history.
- The local path breaks or starts asking for a password.

## 3. Constraints

**The host is a Koyeb free instance** (owner's choice). Read 2026-11-25 on koyeb.com/docs:

- "The Koyeb Free Instance automatically scales down to zero when it doesn't receive any traffic for 1 hour. Scale-to-zero on this Instance cannot be disabled" (run-and-scale/scale-to-zero).
- Waking from that state: "a cold start time of 1-5 seconds" (same page). Our own start comes on top. Whether Koyeb holds a request while the instance wakes is not stated on that page.
- "Each Free Instance provides 512MB of RAM, 0.1 vCPU, and 2GB of SSD. Each organization is limited to one Free Instance" (reference/instances). Our start-up takes about 1.3 to 1.6 seconds of processor time on the owner's laptop (Apple M2, measured by the reviewer: about 1.0 s of imports, 0.26 s loading the data and scoring). On a tenth of a core that is likely 15 to 30 seconds. An estimate, not measured on Koyeb.
- "The connection timeout for HTTP requests is set to 100 seconds" (reference/edge-network).
- "We require a credit card to prevent fraud and abuse", verified by "a $29 pre-authorization hold" that is cancelled at once (faqs/pricing).
- From the hosting research, not rechecked: deploys from a GitHub repository on push, with a buildpack or a Dockerfile; secrets are set as environment variables; the service gets an HTTPS address on koyeb.app.

**The server today** (measured 2026-11-25, no paid call):

- About 120 MB of memory at rest. A warm start takes about 2 seconds to the first healthy reply. The first start in a fresh clone took 9.7 seconds, so most of it is one-time work on a first run (byte-compiling is the likely part, not measured); the database build takes 2.4 seconds.
- Every answer ends by 90 seconds (`config/agent.toml`, `message_time_limit_seconds`), inside Koyeb's 100.
- Conversations live in process memory with no limit on their number (`src/wra/agent/loop.py:102`). They are lost when the instance sleeps or restarts; the page already handles a lost conversation (the server's 404, then a "New conversation" message).
- The key: `load_dotenv(paths.env_file())` runs with `override=False`, and a missing `.env` is skipped, so a key set in the host's environment is used with no code change (checked 2026-11-25).
- The page calls `/api/chat` by a relative address (`src/wra/api/static/index.html:229`), so on the public site it talks to the same server it was loaded from.
- The server listens on 127.0.0.1 unless `--host` says otherwise (`src/wra/cli.py:72`).

**Project rules that bear on it:** no JavaScript packages and no agent framework; secrets live only in the git-ignored `.env` (`CLAUDE.md` rule 7), so keeping the key in Koyeb's secret settings is an exception the owner must approve; every paid call is the owner's to approve; commits carry the repo-local personal address; the HTTP behaviour settled in milestone 4 is kept, and this design only adds statuses for conditions that did not exist before.

**The repository** has no remote today. It goes on GitHub as a public repository under the owner's personal account (the owner hands in "a GitHub link"; public is Claude's call, and the owner's answers on the author address and the station data in section 8 were given for a public repository).

## 4. Approaches considered

| Option | Two weeks costs | Sleeps when idle? | First question after idle | Setup |
|---|---|---|---|---|
| **Koyeb, free instance (chosen)** | $0, card on file | After 1 hour, always | 1 to 5 s wake (Koyeb's figure) plus about 2 s start | Connect GitHub; Koyeb builds and redeploys on push |
| Fly.io, free allowance | $0, card on file ("$5 of usage every month once you add a card") | No, if kept running | No delay | A Dockerfile, its command-line tool, a setting to stop it starting a spare machine ("Create spare machines … (default true)"); its request time limit undocumented |
| Render, paid instance | About $3.30 (billed "prorated to the second", $7 a month) | No | No delay | Connect GitHub; builds from `uv.lock` by itself |
| Render, free | $0 | After 15 minutes | "about one minute" | As Render paid |

Prices and quotes read 2026-11-25 on each host's own pages. **The owner picked Koyeb free:** it costs nothing and it is the least setup of the free options. It was picked on a wake-up of a few seconds; the review then found the free instance's tenth of a core likely stretches our start-up to 15 to 30 seconds. The owner's answer: stay on Koyeb free for now and re-evaluate with the measured wait (2026-11-25). Render paid stays the fallback: no sleep, the same code changes. Render free was ruled out because a one-minute wait is the reviewer's first impression this design exists to avoid. Railway, Google Cloud Run and Hugging Face were dropped earlier. Railway's first request after sleep "may return a 502 Bad Gateway" (read 2026-11-25), and the research found its free credit too small for an always-on server. The other two cost more setup or money for nothing gained here. Except the quoted line, that paragraph is from the research, not rechecked.

## 5. The design

### 5.1 Public mode, and why it fails closed

The server has two modes, chosen by where it listens, not by a flag someone could forget:

- **Local** (listening on 127.0.0.1 or localhost): exactly as today. No sign-in, no daily cap.
- **Public** (listening on any other address, as it must on Koyeb): the access code is required. A new setting, `WRA_ACCESS_CODE`, read from the environment, holds it. If it is missing or empty, the server refuses to start and says why. So a deploy with a missing secret shows up as a failed deploy, never as an open site.

### 5.2 The door: the browser's own sign-in box

Claude's call. In public mode every route except `/healthz` requires HTTP Basic authentication: a fixed username (`analyst`) and the access code as the password, compared in constant time. Without them the server answers 401 with a `WWW-Authenticate: Basic` header, so the browser shows its own sign-in box.

- The page itself does not change. Once someone has signed in, the browser sends the same credentials with the page's own calls to `/api/chat` and `/api/hubs`, which go to the same address. Expected; confirmed by the hand check in 5.10.
- `/healthz` stays open: it makes no model call, and Koyeb can use it to see the server is up.
- FastAPI's generated reference (`/docs`) is behind the door like everything else.
- Rejected: a code field on the page. It looks more like a product, but it adds page logic, and the page's logic is checked only by hand (`.claude/OPEN_ISSUES.md`).

### 5.3 The cap on questions

Claude's call, open to the owner. In public mode, at most **100 questions a day** (UTC) reach the model, across everyone. The 101st gets a reply with status `error` and a new error code, `daily_limit`, sent as HTTP 429, with a plain message saying the demo's question limit for today is used up and when it resets. No model call is made.

- A question counts when it is accepted for answering. Messages refused before that (busy, unknown conversation, a malformed request) do not count.
- The count lives in the server's memory, so it starts again whenever the instance sleeps or restarts. On Koyeb it sleeps after an idle hour, so the cap bounds a burst, not a calendar day: someone with the code who waits out the idle hour could spend another 100. The hard ceiling is the Anthropic workspace's monthly limit (5.5). Accepted at demo grade: keeping the count across restarts would need storage the free instance does not keep.
- What 100 questions cost: about 7.5 cents at the measured average (0.075 cents an answer, `docs/EVAL_RESULTS.md`); at most about 5 USD if every question used all six model calls at full output length (Claude's arithmetic from `config/agent.toml`).
- The limit sits in the API layer, so `wra ask`, `wra chat` and `wra eval`, which call the agent directly, never meet it.

### 5.4 The cap on conversations held

Claude's call. The agent holds at most **200 conversations**. When a new one would pass that, the one used least recently is dropped. Its next message gets the existing `unknown_conversation` reply (404), which the page already turns into "New conversation". This applies in both modes; an evaluation run opens 42 conversations, well under the limit.

### 5.5 The key and the hard spending ceiling (the owner's steps)

- A separate Anthropic workspace for the demo, with a monthly spending limit the owner sets (Claude proposes 5 USD) and a key scoped to that workspace. The owner's own key in `.env` is untouched, and the demo key can be revoked without affecting it.
- Read 2026-11-25 on platform.claude.com/docs/en/manage-claude/workspaces: "API keys can be scoped to a single workspace." That a workspace other than the default one can have its own monthly limit, set on the Console's Spend limits page, comes from two sources but not from text read word for word; the owner sees it when setting the limit. What the API does once the limit is reached is not stated on the pages read; the agent would report a refused call as `model_call_failed` (502). Not tested, since testing it means reaching the limit.
- The demo key lives only in Koyeb's secret settings: an exception to rule 7, approved by the owner on 2026-11-25. Rule 7 in `CLAUDE.md` is reworded to name it when this is built.

### 5.6 Building and running on Koyeb

- **A Dockerfile** (Claude's call, over Koyeb's buildpack, whose support for `uv` was not checked): Python 3.13; `uv sync --frozen --no-dev` with byte-compiling, so the first start after a wake-up does not repeat first-run work (the builder measures the image's start time); `wra ingest` at build time, so the database is in the image and start-up does not rebuild it; the start command runs `wra serve` on all addresses, on the port Koyeb gives it.
- **A `.dockerignore`** that keeps `.env`, `.venv`, `evals/runs/` and `docs/ai-session/` out of the image. The key must never be inside an image.
- **On Koyeb:** one free instance, built from the repository's `main` branch on every push, the health check on `/healthz`, two secrets (`ANTHROPIC_API_KEY`, `WRA_ACCESS_CODE`). No `WRA_TODAY`: "last year" is 2025 until 1 January 2027, which covers the window.

### 5.7 Going public on GitHub: a one-way door

Anything pushed to a public repository should be treated as permanent, since it can be copied or cached at once.

- **The scan.** Every commit, not just today's files, is searched for: the owner's work email domain, the employer's, colleagues' and work systems' names from the owner's global instructions, key-like text (`sk-ant-` followed by key characters), and claude.ai session links. Run on 2026-11-25 over all 74 commits: none found. It runs again on the final commit before the first push. The owner may add other names, one per line, in a file outside the repository; the scan reads that file and prints only counts, so the names never appear in a session transcript. A hit stops the push until the owner decides what to do.
- **What exported transcripts show.** The session 05 export shows each command collapsed ("Ran N shell command", 110 times) and no command text, so what Claude types in commands stays out of them; what Claude writes in replies does not.
- **The session 06 transcript** contains one work project name, in a question Claude wrote. It is reworded before that transcript is committed, and the transcript gets the scan.
- **The account.** `gh` on this machine is signed in to two accounts, and the active one is not the owner's personal account. Before creating the repository, the main session switches `gh` to the owner's personal account (owner, 2026-11-25); it creates the repository and pushes, then switches back. Koyeb's GitHub connection is granted on the personal account.
- **Left as they are (owner, 2026-11-25):** the personal email address on every commit, since changing it would change every commit id the documents cite as proof; and the station service's raw responses under `data/raw/acis/`, published with the rest (this extends open point O1 in `docs/ASSUMPTIONS.md` to a public repository).
- **Creating the repository and pushing** is done in the main session with `gh`, one call per message, after the scan, on the owner's go.

### 5.8 Interview day

A short runbook goes in the README:

- **The day before:** run `scripts/e2e.sh` (free) on the laptop, so the local backup is proven. Open the public URL, sign in, ask one question (paid, under a cent).
- **Fifteen minutes before:** open the public URL to wake it, and ask one question.
- **If the public URL fails during the interview:** `uv run wra serve` on the laptop, open http://127.0.0.1:8000/, share the screen. About a minute.
- Keep the access code at hand, outside the repository.

### 5.9 Documents

- **README:** a "Public demo" section (the URL; that the code is sent separately; the limits; that the first question after an idle hour takes a few seconds longer) and the interview-day runbook.
- **ARCHITECTURE:** public mode, the door, the two caps, the two new HTTP statuses (401, 429).
- **DECISIONS:** one entry for public mode (host, door, caps, failing closed).
- **PLAN Deviations and ASSUMPTIONS:** deployment as built.
- **OPEN_ISSUES:** the page check by hand is rerun on the public URL.

### 5.10 How it is checked

No test makes a paid call.

- **Tests:** the door (401 without or with wrong credentials on `/`, `/api/chat`, `/api/hubs`, `/docs`; through with the right ones; `/healthz` always open; no door in local mode); failing closed (public mode without `WRA_ACCESS_CODE` refuses to start); the question cap (the 101st refused with `daily_limit` and no model call on the scripted fake model; refused messages not counted; a new UTC day starts again, with the clock injected); the conversation cap (the least recently used dropped, its next message gets `unknown_conversation`).
- **If Docker is installed on the laptop,** build the image and get a healthy `/healthz` from it before the first push.
- **On the public URL, by the owner, after the deploy:** the sign-in box appears; a wrong code is refused; the README's four-step page check passes (it spends one question); `/healthz` answers without signing in.
- **The wake-up wait, on the public URL:** after at least an hour with no traffic, the time from opening the page to the sign-in box appearing, and whether the first request succeeds. Measured twice, written into the README, and reported to the owner for the host decision in goal 2.
- **The existing checks still pass:** `uv run pytest -q`, `scripts/e2e.sh` (free part; the paid part only on the owner's go).

## 6. What only the owner does

1. Approve this design.
2. In the Anthropic Console: create the demo workspace, set its monthly limit, create a key scoped to it.
3. Give the go for the first push once the final scan is clean. Optionally, write the file of other names to keep out.
4. On Koyeb: create an account (card, $29 hold), connect GitHub, create the service from the repository, enter the two secrets. Claude gives the steps; the owner clicks.
5. Send the reviewers the URL and the access code, apart from the repository.
6. After the interview: delete the Koyeb service and revoke the demo key.

## 7. Left to the builder

The Dockerfile's exact lines and how the port reaches the server; the sign-in realm's wording; the `daily_limit` message wording (plain, saying when it resets); where the counters live in the code; where the two limits sit in the config (their values above are Claude's proposal); test names.

## 8. The review's questions and the owner's answers (2026-11-25)

| Question | Answer |
|---|---|
| The free instance's tenth of a core likely makes the first page after an idle hour take 15 to 30 seconds. Keep Koyeb free or pay for a host that never sleeps? | Stay on Koyeb free for now; measure, then re-evaluate (owner). |
| Which GitHub account owns the repository? | The owner's personal account; `gh` is switched to it for the creation and push (owner). |
| The personal email address is on every commit. Rewrite before going public? | Leave it (owner). |
| Does accepting the station data's unconfirmed terms extend to a public repository? | Yes, change nothing (owner). |
| The demo key in Koyeb's secret settings, an exception to rule 7? | Approved (owner). |
| Which names does the scan search for, and where does the list live? | Those in the owner's global instructions, plus any the owner adds in a file outside the repository; counts only (Claude's call). |

## 9. Revision after the build: the host is Render (owner, 2026-11-25)

**Decision:** the public site runs on Render's paid 512 MB instance ("Less than 1 CPU $7/month 512 MB RAM 0.5c-512mb", render.com/pricing), built from the repository's Dockerfile, instead of Koyeb's free instance.

**Why:** three things learned after Koyeb was chosen. (1) The image took 41.7 to 43.7 s to start at Koyeb's free size, measured locally (`docs/DEPLOY_PLAN.md`, Task 3), not the few seconds Koyeb was chosen on; every reviewer arriving after an idle hour would wait that long. (2) A Koyeb sign-up starts on its Pro plan ("When signing up, the selected plan is Pro, so you will be charged the pro-rated amount for Pro", koyeb.com/docs/faqs/pricing; Pro is "$29 /mo +compute", koyeb.com/pricing) unless switched to Starter. (3) The owner wants the simple option. Render's paid instance never sleeps ("To remove the Free instance limitations described below, you can upgrade your service to any paid compute plan", render.com/docs/free), its compute is "prorated to the second" on a base plan of "$0 /mo + compute" (render.com/pricing), so two weeks cost about $3.30, and it "fully supports Docker-based deploys" (render.com/docs/docker). Koyeb's paid eco-micro (about $1.25 for two weeks) was rejected for the Pro-plan default and the card hold. All read 2026-11-25.

**What it supersedes:** the Koyeb facts in section 3, the choice in section 4, the Koyeb lines of 5.6 and section 6, and goal 2's wait after an idle hour, which no longer happens. Render passes the port in `PORT` ("The default value of PORT is 10000 for all Render web services", render.com/docs/web-services), which the Dockerfile's `${PORT:-8000}` already reads, and its dashboard has a health check path setting (render.com/docs/health-checks). Everything else stands: public mode, the door, both limits, the image, going public on GitHub.

**Claude's calls, for the owner to check:** a public repository; public mode decided by where the server listens, failing closed without the code; the browser's own sign-in box rather than a code field on the page; 100 questions a day and 200 conversations held; a 5 USD monthly limit on the demo workspace; the question cap only in public mode and in the API layer; HTTP 401 for the door and 429 with `daily_limit` for the cap; a Dockerfile, with the database built into the image.
