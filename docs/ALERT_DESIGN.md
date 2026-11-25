# The score-change alert: design

**Grade: demo.** The plan's "interview take-home prototype" (`docs/PLAN.md`, top). One command and one scheduled job, checked by tests and a few real runs. Not production: one destination, no history service, nothing watching the job itself.

Status: **approved by the owner on 2026-11-25.** Written by Fable, checked by a fresh reviewer as its builder would. Queue item q8. "Read" means the words were read that day on the page named. "Measured" means run that day with this repository's code and data. Anything not checked is marked UNVERIFIED.

## 1. Why, and for whom

The assignment: "Bonus: a scheduled or webhook-triggered alert when a hub's risk score changes". It also says: "A narrow scope done well is better than a broad scope done shallowly." Of the two bonuses left, the owner chose this one and dropped voice, because the alert serves the narrow scope better (2026-11-25).

- **In the story,** the analysts have defended a ranking to their boss. If the data behind it moves, they should hear which hubs moved and by how much.
- **In reality,** the reviewers should see the alert without the owner: the job, its run history and one example message, all in the public repository.

One thing comes first. The score covers ten finished years, 2016 to 2025, plus FEMA's long hurricane record (`config/scoring.toml`, `src/wra/ingest/__init__.py`), and a refresh asks for the same years again. It moves only when a source corrects past records, FEMA publishes a new release, the period is moved forward, or the weights or counting rules are edited. So an honest alert will nearly always say "no change". Measured: a fresh fetch one day after the stored one changed none of the 60 figures, 12 ranks and 12 bands. That gives the design two jobs: make "no change" believable, and give the demo a clearly labelled way to fire (5.6).

## 2. Goals, non-goals, anti-goals

Goals, most important first:

1. **A real change reaches a person,** in words they can act on, with every figure taken from the scoring code.
2. **"No change" can be believed.** A run that could not check fails in plain sight. It never reads as "no change".
3. **A reviewer can see it work** without running anything.
4. **Nothing else moves.** The site, the local commands and the evaluation behave as today. No model, no paid call.

Non-goals: alerts about weather happening now (out of scope since the interview's answer 8, so the Weather Service's live feed that plan section 4.3 kept for this bonus is not used); saying which individual warnings moved a figure; a chat or email message of our own; a history of scores beyond git; tests run on every push; watching anything but the overall ranking.

Anti-goals (a failure even if everything else works):

- A false alarm: an issue for a failed fetch or a changed time stamp, or a demo that reads as real.
- The alert changes what it watches: the job pushes, the site restarts, or the saved copy moves with no person involved.
- The same change is reported every week.
- A figure in the message that the scoring code did not produce.

## 3. Constraints

**The project** (checked in the code):

- No score is stored: the database's seven tables hold none (`docs/ARCHITECTURE.md`, "Data storage"). The alert needs a saved copy to compare against.
- `wra ingest --refresh` makes 48 requests, needs no key and replaces `data/raw/` (`src/wra/ingest/fetch.py`). Measured: 108 seconds.
- The offline build stops when a stored response is for the wrong place or was altered (`src/wra/ingest/build.py`). So data for the wrong place fails the run. It does not become an alert.
- Every push to `main` redeploys the site and resets open conversations (`CLAUDE.md`, Gotchas), unless the commit message carries a skip phrase. Render: "you can include a skip phrase in your Git commit message to prevent the change from triggering an auto-deploy: The skip phrase is one of [skip render] or [render skip]" (render.com/docs/deploys, read). Which commit of a push of several Render reads: UNVERIFIED, so every commit of this feature's pushes carries the phrase.
- Measured: 24 of the 48 fresh files differed from the stored ones, all from the warning archive. In the four compared by hand, only a `generated_at` time stamp differed. So the alert compares scores, never files or checksums.

**GitHub Actions** is GitHub's service for running jobs described by a file in the repository, called a workflow. Read on docs.github.com unless another site is named.

| Question | What the page says |
|---|---|
| Cost | Free: "Standard GitHub-hosted runners in public repositories." A runner is the throwaway machine a job runs on. (billing/concepts/product-billing/github-actions) |
| The job's token | GitHub "automatically creates a unique GITHUB_TOKEN" for each job, limited "to the repository that contains your workflow". (actions/concepts/security/github_token) |
| Opening an issue | Needs '"Issues" repository permissions (write)' (rest/issues/issues). GitHub's own example does it with `contents: read`, `issues: write` and `gh issue create`. Permissions not named "are set to none". (actions/tutorials/authenticate-with-github_token; workflow syntax) |
| The schedule | Written in "POSIX cron syntax", UTC by default, at most "once every 5 minutes". A run "can be delayed", and under load "some queued jobs may be dropped"; "High load times include the start of every hour." It is "automatically disabled when no repository activity has occurred in 60 days". (events-that-trigger-workflows) |
| A manual run | The `workflow_dispatch` trigger, with typed inputs such as "boolean". Started from "the Actions tab on GitHub, GitHub CLI, or the REST API". (same page; manually-run-a-workflow) |
| Pushing the workflow file | The credential `git` pushes with needs the `workflow` scope, a permission that "Grants the ability to add and update GitHub Actions workflow files." The `gh` tool's minimum set is "repo, read:org, and gist" (cli.github.com/manual/gh_auth_login), so it could have been missing. Measured: the owner's active personal sign-in lists `'gist', 'read:org', 'repo', 'workflow'` (`gh auth status`). |
| Is the owner told | Creating an issue "triggers notifications" (rest/issues/issues), and "you also automatically watch all repositories that you create" (about-notifications). An account is also subscribed when it has "Been assigned to an issue or pull request" (same page), and `gh issue create` can "Assign people by their login" (cli.github.com/manual/gh_issue_create). Whether the owner's settings make that an email: UNVERIFIED. |

**Project rules that bear on it:** numbers come from code (rule 1), so code writes the message; no paid call (rule 12); the job needs none of our secrets (rule 7); no new dependency; tests use no network.

## 4. Approaches considered

**Where the alert lands** (the owner's pick, 2026-11-25):

| Destination | New secret | Who sees it | To build |
|---|---|---|---|
| **An issue in the public repository, opened by a scheduled GitHub job (chosen)** | None: the job's own token | Anyone who opens the repository; people watching it are notified | A workflow file |
| A chat-channel webhook, Slack-style | The webhook's address | The channel's members; reviewers only on a shared screen | The same job plus the secret |
| Terminal and a file only | None | Whoever runs the command | Least |

The issue wins because a reviewer sees it without the owner, it needs no secret, and it can be closed when the change is dealt with. The third option survives inside it: the same command runs in a terminal.

**Where the saved copy lives** (Claude's call):

| Option | Verdict |
|---|---|
| **A committed file that only a person's command changes (chosen)** | It means "the ranking as last reviewed". The job never pushes, so it cannot restart the site. Git's history of the file is the history of the score. |
| The job commits the new scores itself | Rejected. Each push redeploys the site, and a bad fetch would become the baseline with nobody looking. |
| The job opens a pull request with the refreshed data | The natural next step, not built. "By default ... workflows are not allowed to create or approve pull requests." |
| GitHub's storage for run files | Rejected. Reviewers cannot see it, and such files "are retained for 90 days". |

## 5. The design

Everything in this section is Claude's call, for the owner to check.

### 5.1 What counts as a change

The alert compares the overall ranking of all twelve hubs, as the `rank_hubs` tool returns it and `wra rank overall` prints it: for each hub the overall figure, the four hazard figures, the rank and the band; for the ranking, its one confidence label. That is 85 values. Any difference is a change. There is no threshold, because the message says how big each change is.

- Figures are compared as the ranking shows them, to two decimals. A movement too small to show is not a change; one that crosses a rounding edge is. Measured: with the hurricane weight at 6, Columbus moves from 0.99 to 1.00 and from Low to Moderate, while each of its hazard figures shows the same two decimals. The message must cope with that.
- A hub whose rank changed only because others passed it is listed apart. A hub added or removed is a change.
- The inputs are saved too: weights, period, band cut-offs, FEMA's release name, the fetch date. They never trigger an alert alone. When scores have moved, the message says which inputs differ. A moved period shows up through the figures it moves.

### 5.2 The saved copy

One committed file, `data/reviewed_scores.json`, one hub per line so a diff reads easily.

- Only `uv run wra alert --accept` writes it. A person runs that and commits the file with the change that caused it. The job reads it and never writes it.
- A test ties it to the repository: scores from the committed raw responses and config must equal the committed copy. A weight edited, or `data/raw/` refreshed, without `--accept` fails `uv run pytest`.
- While a real change waits for review, the job finds the same difference each week. 5.5 stops the repeats.

### 5.3 The command

`wra alert` compares and prints. No network, no model, no key.

- `uv run wra alert` prints one "No change" line, or the issue's title and body. This is the dry run: the message is read and tested without GitHub.
- `--accept` writes the saved copy. `--demo` is in 5.6. The two together are refused.
- For the job, it also writes the title and body to files and tells three results apart: no change, change, could not compare. A failure must never look like "no change".
- The logic is pure functions: take a snapshot from the tool result, compare two, write the message, work out a change id (a short hash of the differences). None of it talks to GitHub, so `src/wra/ingest/fetch.py` stays the only module that uses the network.

### 5.4 The job

One workflow file, `.github/workflows/score-alert.yml`.

- **When:** weekly, at a minute away from the top of the hour; and by hand, with one tick-box input, `demo`.
- **What it may do:** `contents: read` and `issues: write`. Nothing else, so it cannot push.
- **Steps:** check out; install `uv` and the project; `uv run wra ingest --refresh` (a demo run builds from the committed data instead, 5.6); `uv run wra alert`; on a change, 5.5. The result line goes on the run's summary page, so "No change" is read without opening a log.
- **Where:** on GitHub's throwaway machine. The fetched files are discarded with it. The site is never touched.
- **When it cannot check:** a failed fetch or a stopped build fails the run. No issue is opened. GitHub's notice of a failed scheduled run goes to "the user who initially created the workflow", if that user has such notices on.

### 5.5 The issue

The job opens it with `gh`, which "is preinstalled on all GitHub-hosted runners", under the label `score-change`, assigned to the repository's owner so that account is subscribed to it (section 3). A demo issue gets its own label, `score-change-demo`, so the duplicate check on real alerts never sees one.

- **Duplicates.** The body ends with the change id. If an open issue with the same label carries the same id, the job opens nothing and the run's summary names that issue. A different difference is a new issue. The job never edits or closes one.
- **Wording.** Code writes all of it: the changed hubs, the rank-only hubs, the confidence label, the inputs that differ, and what to do next.

An example with the demo's real figures (measured; the layout is the builder's):

> **[DEMO] Hub risk scores changed: 9 of 12 hubs, 3 changed band**
>
> **This is a demonstration, not a real change.** The official scores have not moved. For this run only, the hurricane weight was 10 instead of 5, on the data committed in the repository.
>
> | Hub | Rank | Disruption days a year | Band | What moved |
> |---|---|---|---|---|
> | Miami (MIA) | 8 → 1 | 1.85 → 3.37 | Moderate → Very high | Hurricanes 1.52 → 3.05 |
> | Houston (IAH) | 7 → 3 | 1.96 → 2.88 | Moderate → High | Hurricanes 0.92 → 1.84 |
> | Columbus (CMH) | 11 | 0.99 → 1.02 | Low → Moderate | Hurricanes 0.03 → 0.06 |
> | (six more rows) | | | | |
>
> Rank only, own figures unchanged: Minneapolis 1 → 2, Denver 3 → 5, Kansas City 4 → 6.
> This says that figures differ, not why. A hiccup at a source can look like a change, so run the job again first.

### 5.6 The demo

A manual run with `demo` ticked, or `uv run wra alert --demo`, compares the saved copy with the ranking under **the hurricane weight doubled**, from 5 to 10.

- It uses the what-if `rank_hubs` already has, so no scoring code is added and no file is edited. Evaluation case 7 expects the chat to make the same tool call.
- It fetches nothing. So it cannot fail on a source's bad day, and the laptop prints the same text as the issue.
- The title starts with `[DEMO]`, the label is `score-change-demo`, the first line says the official scores have not moved, and the change id is marked too, so a demo never hides a real change.
- Doubled rather than a quieter weight of 6 (measured: only Houston and Miami move, to High): it is the what-if the chat answers in evaluation case 7, so a reviewer can ask the chat "What if a hurricane counted double?" and see the same figures in its table.
- The honest path is shown by a manual run without `demo` and by the scheduled runs: a real fetch, "No change", no issue.

### 5.7 How it is checked

**By tests,** with no network and no GitHub:

- The comparison and the message on hand-built snapshots: no change, one figure, a rank swap, a band crossing, the Columbus rounding case, rank-only hubs, the confidence label, a hub added, inputs that differ. The same differences give the same change id.
- The command on the committed data: `wra alert` says "No change"; `--demo` gives the title above; `--accept` reproduces the committed file; `--accept --demo` is refused; a missing saved copy is a plain error.
- The workflow file read as text, as `tests/test_container.py` reads `.dockerignore`: `contents: read` and `issues: write` only, and no `git push`.

**Only by a real run on GitHub,** on the owner's go, since it means a push:

- GitHub accepts the workflow file, the project installs there, and the three data services answer GitHub's machines. UNVERIFIED until then.
- GitHub's Linux machine computes the laptop's figures: the run without `demo` says "No change", and the demo issue's text equals the laptop's.
- The token opens the issue, a second demo run opens nothing, the owner is notified, and a scheduled run appears at its time.

The documents follow the build: a README section showing the demo's message (the one place reviewers see it, since the demo issue is closed), a line in the reviewers' front door, ARCHITECTURE, one DECISIONS entry, PLAN Deviations.

## 6. What only the owner does

1. Approve this design.
2. **The `workflow` scope:** nothing to do. The personal sign-in already has it (section 3).
3. **Give the go for each push.** Every commit of this feature's pushes carries `[skip render]`, so the site is not redeployed (section 3). A fix that a real run calls for is another push, again on the owner's go.
4. **The first runs.** On GitHub: Actions, the workflow's name, "Run workflow", `demo` ticked. Check that the issue appears and whether a notification arrives. Run it again: no second issue. Close the demo issue (owner, 2026-11-25: the Issues tab stays empty unless a real change happens). Then once without `demo`: "No change", no issue. That run is a real one (owner, 2026-11-25: no "check only" run, for simplicity), so if GitHub's figures differ it opens a real issue, and step 5 applies. If the Issues tab is missing, turn Issues on in the repository's Settings, under "Features" (whether they are on: UNVERIFIED).
5. **When a real alert arrives:** run the job again. If it repeats: `uv run wra ingest --refresh`, then `uv run wra rank overall`. If the new ranking is right: `uv run wra alert --accept`, commit `data/raw/` with the saved copy, push without the skip phrase, close the issue. That push also updates the site.
6. **After the interview,** with the site's takedown (queue item q23): on GitHub, Actions, the workflow, then "Disable workflow" (docs.github.com, disable-and-enable-workflows). Claude's call: it would otherwise keep fetching weekly until GitHub's 60-day rule stops it.

## 7. Left to the builder

File and module names, including the two above. How the command reports its three results to the job. The exact words of the title and body. The hash behind the change id. How the job finds an open issue with the same id, and how the label comes to exist. The weekday and minute, chosen so the first scheduled run comes soon after the push. A time limit for the job. The pinned versions of `uv` and of the two outside steps (GitHub's advice: "Pin actions to a full-length commit SHA"). Test names.

If time runs short, cut in this order: the summary-page line; the workflow text test; the change id, falling back to "open nothing while any issue labelled `score-change` is open" (a demo issue's own label keeps it from blocking a real alert). The comparison, the saved copy, its test and the demo's label are never cut.

## 8. The review's questions and the owner's answers (2026-11-25)

A fresh reviewer read this design as its builder would, before the owner saw it.

| Question | Answer |
|---|---|
| Should the manual run also offer "check only" (fetch and compare, open nothing), so the first real run on GitHub cannot open an unmarked issue in the public repository? | No: simplicity and clarity. The manual run has only the `demo` tick-box (owner). |
| Should one demo issue stay open, so reviewers see an alert in the Issues tab? | No: close it. Reviewers see the wording in the README (owner). |
| If no notification arrives, what then? | Each issue is assigned to the repository's owner, which subscribes the account (section 3) (Claude's call). |
| Fix-up pushes restart the site? | No: every commit of this feature carries `[skip render]` (section 3) (Claude's call). |
| A demo issue left open would silence real alerts under the cut-down duplicate rule. | Demo issues carry their own label, `score-change-demo` (Claude's call). |

**Claude's calls, for the owner to check:** all of section 5, the second table of section 4, and the three in the table above. The main ones: 85 values compared as shown, with no threshold; scores compared, not files; a committed saved copy that only `--accept` changes; a job that never pushes; duplicates stopped by a change id; the demo as the hurricane weight doubled on committed data, with no fetch; a weekly schedule, since the data covers finished years (daily would add runs to the history at 48 requests a day to free public services); the schedule disabled after the interview.
