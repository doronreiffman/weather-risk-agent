# Spoken questions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Grade: demo**, as the approved design states (`docs/VOICE_DESIGN.md`, top): "The plan's 'interview take-home prototype'".

**Goal:** a Speak button on the chat page that puts a spoken question in the box, for the analyst to check, correct and send with Ask.

**Architecture:** all of it is in one file, `src/wra/api/static/index.html`. Two functions written to stand alone (joining heard words to the box, and turning a failure code into a message) run in Node in the tests. The wiring around the browser's speech recognition sits between two marker comments. Tests read the page as text to check what it holds and what it never calls. Its behaviour is checked by hand (README).

**Tech Stack:** plain HTML, CSS and JavaScript; the browser's Web Speech API (`SpeechRecognition`, or the prefixed `webkitSpeechRecognition`); Python 3.13, `uv`, `pytest`; Node for the function tests, skipped when it is missing. No new dependency.

**Spec:** `docs/VOICE_DESIGN.md` (approved 2026-11-25). Read it with this plan.

**Who runs it:** implementers on Opus, a review after each task on Opus, and a whole-branch review on Fable at the end (`CLAUDE.md` rule 9).

Written by an Opus subagent on 2026-11-25. The main session checked its claims about the code, the hub names and two browser facts (MDN: a form button submits by default; `abort()` returns no further result) before saving; one wording change, in the notice's last sentence ("especially hub names").

## Global Constraints

- Under `src/`, only `src/wra/api/static/index.html` changes. No server code, no JavaScript package, no new Python dependency, no secret, no new paid call.
- The page stays one file. `tests/test_api.py` refuses `src=`, `<link` and `import ` anywhere in it. So no icon file, and no copy or comment that holds those strings.
- Our server never receives audio. The page holds no `getUserMedia` and no `MediaRecorder`. `POST /api/chat` is unchanged.
- Speech never sends. Only Ask and Enter send, as today. While listening, Ask is disabled and the box is read-only.
- The page never changes a recognised word: no matching to hub names, no `phrases`.
- Recognition settings: `lang` `"en-US"`, `continuous` `false`, `interimResults` `true`. `processLocally` is not set.
- Tests never call the model API (`CLAUDE.md` rule 12). They need no browser and no microphone.
- Plain language in all copy and documents, one idea per sentence, no em dashes.
- Commits: at most one per task, each with `[skip render]`. A message claims only what was run on the tree being committed; other changes are stashed first (rule 6). Before each commit, `git diff --cached | grep -i -c -F "$(git config --global user.email | cut -d@ -f2)"` prints `0`, and every file the message names is staged.
- Documents (`.md` files) are written by the main session. A task that changes one has its implementer return the text.
- Pushes and every `gh` call are the main session's, each on the owner's go.

## Review Focus

1. **A Speak button that sends.** A `<button>` inside a form submits the form by default, so a plain one would send whatever is in the box. Speak is `type="button"`. Test: Task 2, `test_the_speak_button_ships_hidden_and_never_submits`.
2. **Words repeated while speaking.** Adding each `result` event to the box gives "which which hubs which hubs in". Every result rebuilds the box from the text it held when listening began plus the whole result list. Tests: Task 1, `test_heard_words_join_the_text_already_in_the_box` (several results); Task 2, `test_speech_follows_the_design` (`joinHeard(spokenBase,`); README spoken step 2 (each word appears once).
3. **A late result rewriting a correction.** The browser can send a result or an error after Stop. Every handler ignores events from a recognition that is no longer the current one. No test can drive this without a browser, so its check is README spoken step 3 (press Stop mid-sentence and type at once: what you type stays).
4. **A spoken question over 2,000 characters.** The browser does not hold text a script writes to `maxlength`, and the server refuses it with HTTP 422. Tests: Task 1, `test_heard_words_are_cut_at_the_servers_limit`; Task 2, `test_speech_follows_the_design` (the cut is `box.maxLength`, and the box's `maxlength` equals the server's `MAX_MESSAGE`).
5. **An answer that fails while listening.** `restore` puts the question back in an empty box, and the next result would erase it. Speak is disabled while an answer is coming, as New conversation already is, so listening and answering never overlap. Tests: Task 2, `test_ask_follows_one_rule`; README check step 1 (Speak greyed out while "Working" shows).

---

### Task 1: The two speech functions, and the guards on the page's script

**Files:**
- Modify: `src/wra/api/static/index.html` (the script, after the New conversation listener, lines 275-279)
- Create: `tests/test_page_speech.py`

**Interfaces:**
- Produces, in the page:
  - The marker comments `// SPEECH BEGIN` and `// SPEECH END`, each once, on lines of their own. All speech code sits between them. The tests read comments too.
  - `function joinHeard(text, parts, limit)`: `text` is the box's text when listening began, `parts` the best transcript of every result so far (an array of strings), `limit` the cut. Returns a string. Each part is trimmed, empty parts are dropped, and the rest are joined with one space. With no heard words, `text` comes back unchanged. Otherwise one space goes between `text` and the heard words, unless `text` is empty or ends in whitespace. The result is cut to `limit` characters.
  - `function speechProblem(code)`: the message for the browser's failure code, copy below.
  - Both are declared at the top level of the script, starting at the line start, with the closing brace alone at the line start and no other line inside starting with `}`. They use nothing outside themselves. (The tests pull them out with a regex, as `boldOnly`'s test does at `tests/test_api.py:202`.)
- Produces, in `tests/test_page_speech.py`:
  - `page() -> str`: the text of `wra.api.app.PAGE`, the file the server sends at `/`.
  - `speech_code() -> str`: the text between the markers.
  - `run_in_node(functions: list[str], expression: str) -> object`: pulls each named function out of `page()` with `rf"^function {name}\(.*?^}}"` under `re.M | re.S` (an `AssertionError` naming the function when it is missing), runs them and `console.log(JSON.stringify(<expression>))` with `node -e`, and returns the parsed JSON. It calls `pytest.skip("Node.js is not installed; the speech functions were checked by hand")` when `shutil.which("node")` is None.

`speechProblem` copy (exact):

| Code | Message |
|---|---|
| `not-allowed` | `The microphone is blocked for this site. Allow it in the browser's site settings, or type the question.` |
| `service-not-allowed`, `language-not-supported` | `This browser cannot turn speech into text here. Type the question.` |
| `network` | `The browser could not reach its speech service. Type the question.` |
| `no-speech` | `Nothing was heard. Press Speak to try again.` |
| `audio-capture` | `No working microphone was found. Type the question.` |
| `aborted` | the empty string |
| any other code | `Speech stopped (CODE). Type the question.`, with CODE the code |

- [ ] **Step 1: Write the failing tests** in `tests/test_page_speech.py`:
  - `test_heard_words_join_the_text_already_in_the_box`: `joinHeard(text, parts, 2000)` gives
    - `("", ["Which hubs"])` → `"Which hubs"`;
    - `("Which hubs", ["in the Midwest"])`, `("Which hubs ", ["in the Midwest"])`, `("Which hubs", [" in the Midwest"])` and `("", ["Which hubs", " in the Midwest"])` → each `"Which hubs in the Midwest"`;
    - `("Which hubs", [])` and `("Which hubs", ["", "  "])` → `"Which hubs"`;
    - `("Which hubs\n", ["in the Midwest"])` → `"Which hubs\nin the Midwest"`.
  - `test_heard_words_are_cut_at_the_servers_limit`: with the limit `MAX_MESSAGE` (from `wra.api.app`), `("x" * 1995, ["hello world"])` → `"x" * 1995 + " hell"`, and `("x" * 2000, ["more"])` → `"x" * 2000`.
  - `test_every_speech_failure_has_its_plain_message`: each code in the table gives its message exactly.
  - `test_an_unknown_speech_failure_names_its_code`: `speechProblem("bad-grammar")` is `"Speech stopped (bad-grammar). Type the question."`.
  - `test_the_speech_code_never_sends`: each marker appears once, BEGIN before END (asserted before `speech_code()` is read). `speech_code()` holds none of `ask(`, `requestSubmit`, `submit(`, `fetch(`, `click(`, `dispatchEvent`. Over the whole page, `ask(` appears twice, `requestSubmit` once and `fetch(` once, as today.
  - `test_the_pages_script_parses`: the text inside the page's one `<script>` element, written to a file under `tmp_path`, passes `node --check` (exit 0). Same skip as `run_in_node`. A syntax error would stop the whole script, typing included (design goal 3). It passes before the change; it guards it.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_page_speech.py -q`
Expected: five FAIL (the markers are missing; `function joinHeard not found in the page`); `test_the_pages_script_parses` passes.

- [ ] **Step 3: Implement** the markers and the two functions, with the interfaces and copy above.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_page_speech.py -q`, then `uv run pytest -q`.
Expected: 6 passed, none skipped (Node is installed on this machine); then all pass.

- [ ] **Step 5: Commit**

```bash
git add src/wra/api/static/index.html tests/test_page_speech.py
git commit -m "Chat page: the speech functions (heard words joined to the box, failure messages), run in Node by tests [skip render]"
```

### Task 2: The Speak button, the notice and the status line

**Files:**
- Modify: `src/wra/api/static/index.html`: the styles (lines 7-61), the form and the lines under it (lines 77-82), the element constants (lines 95-100), `setWorking` (lines 218-222), and the speech code between the markers.
- Test: `tests/test_page_speech.py` (append)

**Interfaces:**
- Consumes: Task 1's `joinHeard`, `speechProblem`, the markers, and the helpers `page()` and `speech_code()`.
- Produces: the elements `#speak`, `#speech-notice`, `#speech-status` (constants `speak`, `speechNotice`, `speechStatus`, beside the others at lines 95-100); the flags `answering` and `listening`; `syncAsk() -> void`; inside the markers, `spokenBase` (the box's text when listening began), `current` (the recognition now listening, or `null`) and `endListening(text: string) -> void`.

The HTML (exact):
- In the form, between the textarea and Ask: `<button id="speak" type="button" hidden>Speak</button>`. Text only, no icon.
- After the form, before `#working`: `<p id="speech-notice" hidden>` with the notice below, then `<p id="speech-status" role="status" hidden></p>`.
- Their styles are the builder's, in the small muted text of the page's other notes. No rule for them sets `display`, so `hidden` keeps working.

Copy (exact):
- The notice: `Speech is turned into text by your browser, not by this site. To do that, the browser may send your voice to its maker: Chrome sends it to Google. This site receives only the text, and only when you press Ask, so check the words first, especially hub names.`
- While listening: `Listening. Pause when you have finished, or press Stop.`
- After listening, when words were added: `Check the words, then press Ask.`

Behaviour (exact):
- **The one rule for Ask,** outside the markers: `let answering = false, listening = false;` and `function syncAsk() { send.disabled = answering || listening; }`. That is the page's only assignment to `send.disabled`. `setWorking(on)` sets `answering = on` and calls `syncAsk()` in place of line 219. It also sets `speak.disabled = on;`, and hides `#speech-status` when `on` is true, so a sent question clears an old "Check the words" line.
- **On load:** `const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;`. When it is set, `#speak` and `#speech-notice` are shown and Speak's click handler is added. Otherwise nothing more runs, and the page is today's page.
- **Speak pressed while `current` is null:** `spokenBase = box.value`. A new `Recognition` for each press, with the three settings. Then `current = rec`, `listening = true`, `syncAsk()`, `box.readOnly = true`, the button reads `Stop`, and the status shows the listening line. Then `rec.start()` inside a `try`; a throw calls `endListening(speechProblem(error.name))`.
- **A `result` from `current`:** `box.value = joinHeard(spokenBase, Array.from(event.results, (r) => r[0].transcript), box.maxLength)`.
- **An `error` from `current`:** `endListening(speechProblem(event.error))`.
- **`end` from `current`:** `endListening(box.value !== spokenBase ? "Check the words, then press Ask." : "")`.
- **Speak pressed while `current` is set (Stop):** end at once with the same rule as `end`, then call `abort()` on the recognition that was current.
- **`endListening(text)`:** `current = null`, `listening = false`, `syncAsk()`, `box.readOnly = false`, the button reads `Speak`, the status shows `text` (hidden when `text` is empty), and `box.focus()` with the cursor at the end. Every handler first checks that its recognition is `current`, so whatever the browser sends afterwards is ignored.
- **Left as they are:** New conversation does not stop listening. Words still changing look the same as final ones.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_page_speech.py`):
  - `test_the_speak_button_ships_hidden_and_never_submits`: the page holds `<button id="speak" type="button" hidden>Speak</button>`, `<p id="speech-notice" hidden>` and `<p id="speech-status" role="status" hidden></p>`.
  - `test_the_notice_says_where_the_voice_goes`: `" ".join(page().split())` holds the notice exactly.
  - `test_ask_follows_one_rule`: `page().count("send.disabled =") == 1`; the page holds `send.disabled = answering || listening;` and `speak.disabled = on;`; `speech_code()` does not hold `send.disabled`.
  - `test_speech_follows_the_design`: `speech_code()` holds `window.SpeechRecognition || window.webkitSpeechRecognition`, `.lang = "en-US"`, `.continuous = false`, `.interimResults = true`, `box.readOnly = true`, `box.readOnly = false`, `joinHeard(spokenBase,` and `box.maxLength`; the page holds `f'maxlength="{MAX_MESSAGE}"'`, and neither `processLocally` nor `.phrases`.
  - `test_the_page_never_holds_audio`: the page holds no `getUserMedia` and no `MediaRecorder`. It passes before the change; it guards it.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_page_speech.py -q`
Expected: the first four FAIL (elements, copy and code missing); `test_the_page_never_holds_audio` and Task 1's tests pass.

- [ ] **Step 3: Implement** the HTML, copy and behaviour above.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_page_speech.py -q`, then `uv run pytest -q`.
Expected: 11 passed, none skipped; then all pass. `test_the_pages_script_parses` passing is the only proof here that the script still runs; the rest is the owner's check by hand.

- [ ] **Step 5: Commit**

```bash
git add src/wra/api/static/index.html tests/test_page_speech.py
git commit -m "Chat page: the Speak button, its notice and status line; Ask disabled while listening [skip render]"
```

### Task 3: The documents (the main session writes them)

**Files:**
- Modify: `README.md`, `docs/SUMMARY.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (append one entry), `docs/PLAN.md` (Deviations), `docs/ASSUMPTIONS.md`, `.claude/OPEN_ISSUES.md`, `.claude/QUEUE.md`

An implementer, if one is used, returns the text and the main session saves it. Each claim is checked against the design's sources or the built page before it is saved.

- [ ] **Step 1: README.**
  - The front door (lines 5-8): one bullet, "Spoken questions (bonus)": Speak puts a spoken question in the box, the analyst checks it and presses Ask, the browser does the recognition, and our server never receives audio.
  - The record line (line 16): `docs/VOICE_DESIGN.md` (spoken questions).
  - A section "Spoken questions", after "Score-change alert": how it is used; the browsers, as design section 5.4 has them; where the audio goes, browser by browser, with the UNVERIFIED points of design section 3 (Safari for web pages, released Edge); and "How well it hears: not yet measured" until the owner's run.
  - "Checking the page by hand before a demo" (lines 58-65): the opening line counts the speech wiring among what has no automated test. Step 1 reads "Ask, Speak and New conversation are greyed out". A second list, "Spoken questions", holds design section 5.6, steps 1 to 8, with four additions: step 2, each word appears once; step 3, press Speak, say a few words, press Stop mid-sentence and type at once, and what you type stays; step 4 names the sixteen words (Minneapolis, Memphis, Denver, Kansas City, Chicago, Dallas, Houston, Miami, Indianapolis, Atlanta, Columbus, Phoenix; winter, flood, severe storm, hurricane), with the box cleared between them; step 7, if Speak is missing, reload the page. Its cost: free, except step 3's Ask, which can stand in for the first list's paid question.
  - "Interview day": if voice will be shown, say one question in the call's setup first; typing is the fallback (design section 6, step 5).
- [ ] **Step 2: The other documents.**
  - SUMMARY, "Asking the agent" (line 61): one sentence on speaking a question in Chrome, checked in the box and sent only with Ask, the audio going to Google in Chrome and never to this system.
  - ARCHITECTURE: a paragraph in "The API and the chat page" (after line 161); `VOICE_DESIGN` and `VOICE_PLAN` in the docs list (lines 76-77); in "Left out on purpose", no speech service of our own.
  - DECISIONS: one entry in the log's own format. Decision: the browser recognises speech, the words go only into the box, only Ask sends, our server never receives audio. Why, with the rejected options of design section 4 (a vendor from our server: a second vendor, a third secret, a new paid path; the system's own dictation: nothing built to see; a model in the page or on our server). Context: the design, this plan, the page, `tests/test_page_speech.py`.
  - PLAN Deviations: a new block after line 680 for section 13's third bonus. The alert block says voice is not built; now it is, spoken questions only, with Firefox left out (owner).
  - ASSUMPTIONS: A12's standing gains speech recognition in `en-US`. A new open point, O16: how well browsers hear the hub and hazard names, and where Safari and released Edge send the audio. Unsettled until the owner's run.
  - OPEN_ISSUES, "The chat page" (line 7), replaced: what tests now cover (the bold renderer, the speech functions, the page text checks, the script parse); what only the check by hand covers; the spoken steps not yet run. Next: the owner's run.
  - QUEUE, q28 (line 10): points to this plan too, and says what is left (the owner's check, the deploy push, the public check).
- [ ] **Step 3: Checks before commit.** `uv run pytest -q`: all pass. The work-address check prints `0`.
- [ ] **Step 4: Commit**

```bash
git add README.md docs/SUMMARY.md docs/ARCHITECTURE.md docs/DECISIONS.md docs/PLAN.md docs/ASSUMPTIONS.md .claude/OPEN_ISSUES.md .claude/QUEUE.md
git commit -m "Spoken questions: README use and check by hand, summary, architecture, decision, deviation, assumptions, open issues, queue [skip render]"
```

### After the tasks (not a task: the owner's steps, design section 6)

Render deploys a push to `main` unless the commit message holds `[skip render]`, and which commit of a push Render reads is unverified (`CLAUDE.md`, Gotchas). So no push mixes commits with and without the phrase: every push is all tagged or one untagged commit.

1. **Whole-branch review on Fable.** Fixes, each committed with `[skip render]`.
2. **Push 1, the build, on the owner's go.** First `git log origin/main..main --format=%s | grep -c -v -F "[skip render]"` prints `0`. Every commit carries the phrase, so Render skips whichever one it reads, and the site does not restart. `gh auth switch --hostname github.com` before and after, each its own message. This push can wait until the deploy commit is ready, so the README and the site change close together.
3. **The owner's check by hand, locally:** README "Spoken questions" steps 1 to 6, and 8 if Safari is at hand. The owner reports the hub-name count and the browser. A fix this calls for is its own commit with `[skip render]`, pushed in an all-tagged push before step 5.
4. **The deploy commit: one commit, without `[skip render]`.** It holds the README's count and browser, and the chat page entry's last run. If more than 2 of 16 came out wrong (design section 8, question 4), the same commit changes the notice's last sentence to `This site receives only the text, and only when you press Ask. In a test in BROWSER, N of 16 hub and hazard names came out wrong: read every hub name before you press Ask.`, and Task 2's notice test with it. `uv run pytest -q` passes on that tree.
5. **Push 2, the deploy, on the owner's go.** It restarts the public site and resets open conversations. First `git log origin/main..main --format=%s` prints exactly one line, without `[skip render]`. A push of one commit gives Render only that commit to read, so the site deploys whichever commit it reads.
6. **The owner's step 7 on the public site:** sign in, then steps 1 and 2. The page is sent with no caching instruction (Starlette's `FileResponse` sets only `last-modified` and `etag`), so if Speak is missing, reload the page. If it is still missing, Render's dashboard shows whether the deploy of that commit ran (UNVERIFIED: whether the dashboard names each deploy's commit).
7. **Close-out commit, with `[skip render]`:** step 7's result in the chat page entry of `.claude/OPEN_ISSUES.md`; q28 to Done in `.claude/QUEUE.md`, with the runs as proof. A failure goes into the open issues instead, and q28 stays open. The commit goes out with the next push, all tagged.

## Deviations

- *The whole-branch review (Fable, 2026-11-25): ready to merge with fixes.* One fix wave, on top of Task 2, with two new text checks (`tests/test_page_speech.py`):
  - **Focus when the browser ends listening by itself** (Important). `endListening` always moved focus into the box, so an Enter meant for Stop just after a pause could send an unread question, the design's first anti-goal. Now the box takes focus after a Stop click, or when focus is elsewhere; when focus is on Speak it stays there. This bends design 5.2's "with the cursor at the end" for a session the browser ends while Speak has focus. Main session's ruling over asking the owner: the anti-goal outranks the cursor detail.
  - **Folded in from the task reviews:** the status line stays in the page once shown (its text is cleared, not hidden), so screen readers can announce "Listening"; the recogniser is built inside the `try`, so a throw there ends with a plain line; a stop the browser started ends like a pause ("Check the words" when words were added); the box scrolls to the newest words.
  - **The README claimed a check by hand that had not happened** (Important, documents). Task 3 step 1 said to write the browsers "as design section 5.4 has them", and 5.4's "Checked by hand" is the plan for a check, not its result. The README now says the check has not been run. Instruction gap: that step should have said to state each planned check as not yet run.
  - **The README's spoken list gains steps 9 to 11** (Enter to stop, a long question, Stop then Speak at once), appended so that the numbers above stay valid. "After the tasks" step 3's local run is steps 1 to 6 and 9 to 11, with 8 if Safari is at hand.
  - **Push 1 waits for the owner's local check** (main session's ruling): the summary and README describe a feature no browser has run yet.
- *The owner's changes after the hand check (2026-11-25).* Every local step passed in Chrome on `b8e090a`, with 16 of 16 hub and hazard names right, so the notice needs no warning. The owner then asked for two changes, a short design settled by the owner's picks: listening runs until Stop (`continuous = true`; the status line "Listening. Press Stop when you have finished."), in place of design 5.1's one utterance per press; and when listening stops, `tidySpoken` adds a capital first letter and a `?` (after a question word) or `.` at the end, never changing a word. One commit on a follow-up branch, reviewed by the main session (the owner asked to rush), then the owner reruns spoken steps 2, 3 and 9.
