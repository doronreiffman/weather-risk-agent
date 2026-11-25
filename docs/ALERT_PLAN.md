# Score-change alert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Grade: demo**, as the approved design states (`docs/ALERT_DESIGN.md`, top): the plan's "interview take-home prototype".

**Goal:** a `wra alert` command and a weekly GitHub job that open an issue when the overall ranking differs from the last reviewed one.

**Architecture:** pure functions in one new module (`src/wra/alert.py`) turn a `rank_hubs` result into a snapshot, compare two snapshots and write the issue's title and body. A thin `wra alert` command in `src/wra/cli.py` reads and writes the saved copy (`data/reviewed_scores.json`) and, for the job, writes its result to files. One workflow file runs the fetch and the command on GitHub's machine and opens the issue with `gh`.

**Tech Stack:** Python 3.13, `uv`, `pytest`, the existing `rank_hubs` tool; GitHub Actions with `gh` preinstalled. No new dependency.

**Spec:** `docs/ALERT_DESIGN.md` (approved 2026-11-25). Read it with this plan.

## Global Constraints

- No model, no paid call, no key; the alert's message is written by code (CLAUDE.md rules 1 and 12).
- `src/wra/ingest/fetch.py` stays the only module that uses the network; `src/wra/alert.py` imports nothing network-related.
- Tests never use the network or GitHub.
- Compared values: per hub the overall figure, the four hazard figures, the rank and the band; for the ranking, its one confidence label. Figures as the ranking shows them, to two decimals. No threshold.
- Inputs saved but never a trigger alone: weights, period, band cut-offs, FEMA's release name, the data date.
- The saved copy changes only through `wra alert --accept`; the job never writes it and never pushes.
- Labels: `score-change` for real alerts, `score-change-demo` for demo issues. Issues assigned to the repository's owner.
- Demo: the hurricane weight doubled (`{"hazard": "hurricane", "mode": "multiply", "value": 2.0}`) on the committed data, no fetch; title starts `[DEMO] `; change id starts `demo-`.
- Job permissions exactly `contents: read` and `issues: write`.
- Every commit of this feature carries `[skip render]` in its message (design section 3); each push on the owner's go.
- Plain language in all text a person reads (issue body, README), no em dashes.

## Review Focus

1. **A run that could not compare** (no database, a fetch that failed, a broken saved copy): the command exits non-zero, writes no `no_change` result, and prints a plain `error:` line, never a traceback. Tests: Task 2, `test_alert_without_a_database_fails_and_writes_no_result`, `test_alert_with_a_broken_saved_copy_is_a_plain_error`.
2. **The same change found again a week later with a newer data date:** same change id, so no second issue. Test: Task 1, `test_change_id_ignores_the_data_date`.
3. **A hub whose figure moved but whose rank and band did not** (Atlanta in the demo: rank 10, 1.24 → 1.48): listed as changed, its rank shown once ("10"), not "10 → 10". Test: Task 1, `test_message_shows_an_unchanged_rank_once`.
4. **A figure that crosses a band edge with no hazard figure visibly moving** (hurricane weight 6: Columbus 0.99 → 1.00, Low → Moderate, hurricanes still 0.03): listed, with "What moved" reading `too small to show per hazard`. Test: Task 1, `test_message_copes_with_a_change_too_small_to_show_per_hazard`.
5. **A scheduled run must never be a demo, and a demo must never fetch:** the workflow's demo condition tests the event name as well as the input (inputs exist only on a manual run). Test: Task 3, `test_the_alert_job_only_demos_on_a_manual_run`.

---

### Task 1: Snapshots, the comparison and the message (pure functions)

**Files:**
- Create: `src/wra/alert.py`
- Test: `tests/test_alert.py`

**Interfaces:**
- Consumes: `wra.tools.envelope.ToolResult` (a `rank_hubs` result for `hazard="overall"`, `region="all"`); `wra.tools.context.ToolContext` (`ctx.config.weights`, `.first_year`, `.last_year`, `.band_cutoffs`, `.hazards[h].label`; `ctx.data.fema_release`, `ctx.data.data_as_of`); `wra.scoring.config.HAZARDS`.
- Produces:
  - `DEMO_CHANGES: list[dict]`, the one weight change above.
  - `@dataclass(frozen=True) class HubScore: hub_id: str; city: str; label: str; rank: int; value: float; band: str; hazards: dict[str, float]` (`city` as `Miami`, `label` as `Miami (MIA)` from `ctx.label`; hazard keys `winter`, `flood`, `severe_storm`, `hurricane`).
  - `@dataclass(frozen=True) class Snapshot: hubs: dict[str, HubScore]; confidence: str; inputs: dict[str, object]` with input keys `weights` (dict), `period` (`"2016-2025"`), `band_cutoffs` (list of floats), `fema_release` (str), `data_as_of` (str).
  - `current_snapshot(ctx: ToolContext, weight_changes: list[dict] | None = None) -> Snapshot`: calls `run_tool(ctx, "rank_hubs", {"hazard": "overall", "region": "all", "top_n": None, "weight_changes": weight_changes or []})`; the inputs record the weights actually used (`result.data["weights"]`).
  - `to_json(s: Snapshot) -> str` and `from_json(text: str) -> Snapshot`: a `{"schema": 1, "confidence", "inputs", "hubs": [...]}` object with one hub per line, hubs in rank order, ending in a newline; `from_json` raises `ValueError` on anything it cannot read.
  - `@dataclass(frozen=True) class HubChange: hub_id: str; city: str; before: HubScore | None; after: HubScore | None`.
  - `@dataclass(frozen=True) class Difference: changed: list[HubChange]; rank_only: list[HubChange]; confidence: tuple[str, str] | None; inputs: dict[str, tuple[object, object]]` with property `is_empty -> bool` (no changed, no rank-only, no confidence change; `inputs` alone never counts).
  - `compare(before: Snapshot, after: Snapshot) -> Difference`: `changed` holds hubs whose value, band or any hazard figure differs, plus hubs added or removed, in the after ranking's order (removed hubs last); `rank_only` holds hubs whose rank alone moved.
  - `change_id(diff: Difference, demo: bool = False) -> str`: the first 12 hex digits of SHA-256 over a canonical JSON (`sort_keys=True`) of `changed`, `rank_only` and `confidence` only; `"demo-"` in front when `demo`.
  - `message(diff: Difference, hazard_labels: dict[str, str], demo: bool = False) -> tuple[str, str]`: the title and the Markdown body. The table names hubs by `label`, the rank-only line by `city`.

- [ ] **Step 1: Write the failing tests** in `tests/test_alert.py`, on hand-built snapshots (a helper `snap(**overrides)` building three or four hubs), plus two on the committed data through the `real_db` fixture from `tests/conftest.py`:
  - `test_no_change_is_empty`: `compare(s, s).is_empty`.
  - `test_one_figure_change_is_listed`: one hub's flood 0.47 → 0.52 and value moved; it is in `changed`, nothing in `rank_only`.
  - `test_a_rank_swap_lists_the_mover_and_the_passed`: hub A's value rises past B; A in `changed`, B in `rank_only`.
  - `test_a_band_crossing_is_a_change`.
  - `test_the_confidence_label_change_is_reported`: `diff.confidence == ("low", "medium")` and `not diff.is_empty`.
  - `test_a_hub_added_or_removed_is_a_change`: `before`/`after` is `None` for it.
  - `test_inputs_alone_are_not_a_change`: only `data_as_of` differs → `is_empty`, and `diff.inputs == {"data_as_of": ("2026-11-24", "2026-12-02")}`.
  - `test_change_id_ignores_the_data_date`: the same figure change with two different data dates gives equal ids; a different change gives a different id; `change_id(d, demo=True).startswith("demo-")`.
  - `test_message_shows_an_unchanged_rank_once`: the row for a hub whose rank stayed 10 reads `| 10 |`, never `10 → 10`.
  - `test_message_copes_with_a_change_too_small_to_show_per_hazard`: value 0.99 → 1.00, band Low → Moderate, hazards equal → its "What moved" cell is `too small to show per hazard`.
  - `test_snapshot_round_trips_through_json`: `from_json(to_json(s)) == s`, and `to_json(s).count("\n")` is the hub count plus the fixed lines (one hub per line).
  - `test_from_json_rejects_what_it_cannot_read`: `pytest.raises(ValueError)` for `"{"`, for `{"schema": 2}` and for a missing key.
  - `test_the_demo_on_the_committed_data` (uses `real_db`): `compare(current_snapshot(ctx), current_snapshot(ctx, DEMO_CHANGES))` has 9 hubs in `changed`, of which 3 changed band (MIA, IAH, CMH), and `rank_only` hub ids `["MSP", "DEN", "MCI"]`; `message(..., demo=True)` title is exactly `[DEMO] Hub risk scores changed: 9 of 12 hubs, 3 changed band`; the body contains `| Miami (MIA) | 8 → 1 | 1.85 → 3.37 | Moderate → Very high | Hurricanes 1.52 → 3.05 |`, the line `Rank only, own figures unchanged: Minneapolis 1 → 2, Denver 3 → 5, Kansas City 4 → 6.`, the demo banner below, the inputs line naming the hurricane weight `5 → 10`, and ends with `Change id: demo-` followed by 12 hex digits.
  - `test_the_real_title_has_no_demo_mark`: with `demo=False` the title starts `Hub risk scores changed:` and the body has no `demonstration`.

  Exact copy the tests pin (the rest of the body's words are the builder's, in plain language):
  - Title: `Hub risk scores changed: {n} of {total} hubs, {b} changed band`, with `[DEMO] ` in front for a demo. When only ranks or the confidence label moved, `{n}` counts the rank-only hubs and the title reads `Hub risk ranking changed: {n} of {total} hubs moved in rank`.
  - Demo banner, the body's first line: `**This is a demonstration, not a real change.** The official scores have not moved. For this run only, the hurricane weight was 10 instead of 5, on the data committed in the repository.` (the two weights from `diff.inputs["weights"]`).
  - Table header: `| Hub | Rank | Disruption days a year | Band | What moved |`; hub as `ctx.label` writes it (`Miami (MIA)`); arrows ` → `; figures with two decimals; "What moved" lists each hazard whose shown figure moved as `{label} {before} → {after}`, joined by `; `.
  - Closing advice, before the change id: `This says that figures differ, not why. A hiccup at a source can look like a change, so run the job again first.`
  - Last line: `Change id: {id}`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_alert.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'wra.alert'`.

- [ ] **Step 3: Implement `src/wra/alert.py`** with the interfaces above. Read rows from `result.data["rows"]` (`rank`, `hub_id`, `city`, `value`, `band`, `breakdown`) and the confidence label from `result.provenance.confidence`; store `ctx.label(hub_id)` as `label`, so `message` needs no context. Values are already rounded to two decimals by `rank`; compare them as floats. `hazard_labels` maps hazard keys to `ctx.config.hazards[h].label`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_alert.py -q`
Expected: all pass. Then `uv run pytest -q`: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/wra/alert.py tests/test_alert.py
git commit -m "The score-change alert's comparison and message, as pure functions [skip render]"
```

### Task 2: The `wra alert` command and the saved copy

**Files:**
- Modify: `src/wra/paths.py` (add `reviewed_scores()`), `src/wra/cli.py` (parser lines 66-77 region; dispatch lines 79-93; new `_alert`)
- Create: `data/reviewed_scores.json` (written by the command itself in Step 5)
- Test: `tests/test_alert.py` (append), `tests/test_cli.py` if the `project` fixture is reused

**Interfaces:**
- Consumes: Task 1's `current_snapshot`, `DEMO_CHANGES`, `to_json`, `from_json`, `compare`, `change_id`, `message`; `wra.tools.context.load_context`.
- Produces: `paths.reviewed_scores() -> Path` (`root() / "data" / "reviewed_scores.json"`); the command `wra alert [--accept | --demo] [--out DIR]`; with `--out`, the files `DIR/result` (one word: `no_change` or `change`), and on a change `DIR/title.txt`, `DIR/body.md`, `DIR/change_id`.

Behaviour (exact):
- `--accept` with `--demo`: prints `error: --accept and --demo cannot be used together.` to stderr, exit 2.
- `--accept`: writes `to_json(current_snapshot(ctx))` to `paths.reviewed_scores()`, prints `Saved today's ranking as the reviewed one: data/reviewed_scores.json. Commit it with the change that caused it.`, exit 0.
- No saved copy: `error: no reviewed ranking at data/reviewed_scores.json. Run "uv run wra alert --accept" once the ranking is reviewed.`, exit 1, no `result` file.
- A saved copy `from_json` rejects: `error: the reviewed ranking at data/reviewed_scores.json cannot be read ({reason}).`, exit 1, no `result` file.
- No change: prints `No change since the ranking was last reviewed (data as of {saved data_as_of}).`, writes `result` = `no_change`, exit 0.
- A change: prints the title, a blank line and the body; writes the four files (creating `DIR` if missing); exit 0.
- `--demo` compares the saved copy with `current_snapshot(ctx, DEMO_CHANGES)` and passes `demo=True` to `message` and `change_id`.
- A missing database is the existing `NoDatabase`, already turned into `error: ...` and exit 1 by `main`.

- [ ] **Step 1: Write the failing tests** (in `tests/test_alert.py`, using `WRA_ROOT` pointed at a temporary folder holding `config/` copied from the repository, `data/wra.sqlite` copied from `real_db`, and a saved copy where a test needs one):
  - `test_accept_writes_the_saved_copy_and_then_there_is_no_change`.
  - `test_accept_and_demo_together_are_refused`: exit 2.
  - `test_alert_without_a_saved_copy_is_a_plain_error`: exit 1, stderr starts `error: no reviewed ranking`, no `result` file in `--out`.
  - `test_alert_with_a_broken_saved_copy_is_a_plain_error`: the file holds `{`; exit 1, stderr starts `error: the reviewed ranking`, no `result` file.
  - `test_alert_without_a_database_fails_and_writes_no_result`: no `data/wra.sqlite`; exit 1, no `result` file.
  - `test_demo_writes_the_job_files`: `--demo --out DIR` → `result` is `change`, `title.txt` starts `[DEMO] `, `change_id` starts `demo-`, `body.md` ends with that id.
  - `test_the_committed_saved_copy_matches_the_committed_data`: `from_json(REPO / "data" / "reviewed_scores.json") == current_snapshot(ctx)` with `ctx = load_context(real_db, REPO / "config" / "scoring.toml")`. Its failure message says: `data/raw or config/scoring.toml changed without "uv run wra alert --accept"`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_alert.py -q`
Expected: the new tests FAIL (`invalid choice: 'alert'`, and `reviewed_scores.json` missing).

- [ ] **Step 3: Implement** `paths.reviewed_scores()`, the `alert` subparser (help: `compare today's ranking with the last reviewed one: no network, no model`), its dispatch, and `_alert(accept: bool, demo: bool, out: Path | None) -> int` in `src/wra/cli.py`, with the behaviour above. Paths printed relative to the root, as above.

- [ ] **Step 4: Write the saved copy and run the tests**

Run: `uv run wra ingest && uv run wra alert --accept && uv run wra alert && uv run wra alert --demo | head -3 && uv run pytest -q`
Expected: the ingest table; the "Saved" line; `No change since the ranking was last reviewed (data as of 2026-11-24).`; the demo title and banner; all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/wra/paths.py src/wra/cli.py tests/test_alert.py data/reviewed_scores.json
git commit -m "wra alert: compare the ranking with the last reviewed one; the reviewed copy, saved [skip render]"
```

### Task 3: The GitHub job, and the documents

**Files:**
- Create: `.github/workflows/score-alert.yml`
- Test: `tests/test_alert.py` (append the workflow-text tests)
- Modify: `README.md` (a "Score-change alert" section and one line in the reviewers' front door), `docs/ARCHITECTURE.md` (component, repository structure, data storage: the new file), `docs/DECISIONS.md` (append one entry), `docs/PLAN.md` (append to Deviations), `.claude/OPEN_ISSUES.md` (the real-run checks, pending), `.claude/QUEUE.md`

**Interfaces:**
- Consumes: Task 2's command and its `--out` files.
- Produces: the workflow `Score-change alert`, triggered by a weekly `schedule` and by `workflow_dispatch` with one boolean input `demo` (default false).

The workflow (the builder writes the YAML; these are the decisions):
- `permissions:` at the top: `contents: read`, `issues: write`, nothing else.
- One job on `ubuntu-latest`, `timeout-minutes: 15`.
- Steps: `actions/checkout` and `astral-sh/setup-uv` pinned to full commit SHAs (look each up with `git ls-remote --tags https://github.com/<owner>/<repo>` and pick the newest release tag, noting it in a comment); `setup-uv` with `version: "0.11.0"` as in the `Dockerfile`; `uv sync --frozen`.
- A demo is `github.event_name == 'workflow_dispatch' && inputs.demo`. Not a demo: `uv run wra ingest --refresh`. A demo: `uv run wra ingest` (committed data, no fetch). Then `uv run wra alert --out alert-out`, plus `--demo` on a demo.
- The issue step (`GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`): if `alert-out/result` is `no_change`, write the command's line to `$GITHUB_STEP_SUMMARY` and stop. On `change`: the label is `score-change-demo` on a demo, else `score-change`; `gh label create "$label" --force`; look for an open issue with that label whose body contains the change id (`gh issue list --label "$label" --state open --json number,body --jq ...`); if one exists, write `Already open: #N` to the summary; else `gh issue create --title "$(cat alert-out/title.txt)" --body-file alert-out/body.md --label "$label" --assignee "$GITHUB_REPOSITORY_OWNER"` and write the issue's address to the summary.
- The schedule: one weekly cron line, at a minute away from the top of the hour, on a weekday that brings the first scheduled run soon after the push.

- [ ] **Step 1: Write the failing tests** (read the YAML as text, as `tests/test_container.py` reads `.dockerignore`):
  - `test_the_alert_job_can_open_issues_and_nothing_more`: the `permissions:` block's lines are exactly `contents: read` and `issues: write`; the text has no `git push` and no `contents: write`.
  - `test_the_alert_job_only_demos_on_a_manual_run`: every line that reads `inputs.demo` also holds `github.event_name == 'workflow_dispatch'`; `wra ingest --refresh` appears once, on a step whose condition is the negation.
  - `test_the_alert_job_keeps_demo_and_real_issues_apart`: the text holds `score-change-demo`, `score-change` and `--assignee`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_alert.py -q -k job`
Expected: FAIL, `FileNotFoundError` for `.github/workflows/score-alert.yml`.

- [ ] **Step 3: Write the workflow**, then run the tests: they pass. Then `uv run pytest -q`: all pass.

- [ ] **Step 4: The documents.**
  - README "Score-change alert": what it watches and why it nearly always says "No change" (the scored years are finished); the three commands (`wra alert`, `--demo`, `--accept`); the GitHub job and its manual demo run; what to do when a real alert arrives (design section 6, step 5); and the demo's message as `uv run wra alert --demo` prints it, pasted from a real run (the one place reviewers see it, since the demo issue is closed).
  - The other files as listed. The DECISIONS entry: the saved copy changes only through `--accept` and the job never pushes; rejected: the job committing scores (each push redeploys the site, and a bad fetch becomes the baseline unseen) and a pull request from the job (not allowed by default; the natural next step).
  - QUEUE: q8's line points to this plan and says what is left (the push and the owner's runs).

- [ ] **Step 5: Checks before commit**

Run: `uv run pytest -q` → all pass. `git diff --cached | grep -i -c -F "$(git config --global user.email | cut -d@ -f2)"` → `0`.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/score-alert.yml tests/test_alert.py README.md docs/ARCHITECTURE.md docs/DECISIONS.md docs/PLAN.md .claude/OPEN_ISSUES.md .claude/QUEUE.md
git commit -m "The weekly score-change job on GitHub, and its documents [skip render]"
```

### After the tasks (not a task: the owner's steps, design section 6)

1. Whole-branch review on Fable (CLAUDE.md rule 9); fixes, each committed with `[skip render]`.
2. The push, on the owner's go: `gh auth status` first, its own message; the personal account must be active.
3. The owner's first runs on GitHub (design section 6, step 4): demo, demo again (no second issue), close it, one real run ("No change"). Each result goes into `.claude/OPEN_ISSUES.md` or, when all pass, moves q8 to Done with the run addresses as proof.

## Deviations

(None yet.)
