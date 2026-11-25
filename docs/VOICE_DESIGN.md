# Spoken questions in the chat page: design

**Grade: demo.** The plan's "interview take-home prototype" (`docs/PLAN.md`, top), the grade `docs/ALERT_DESIGN.md` also took. One button on the chat page, checked by a few tests and a check by hand. Not production: English only, desktop browsers, and no promise about how well any browser hears.

Status: **Draft, not approved.** Written by Fable on 2026-11-25 for queue item q28; the owner picked approach A and answered section 8's questions the same day. Nothing is built before the owner approves it. "Read" means the words were read that day on the page named (MDN pages as their source text in MDN's own repository). "Measured" means run that day on this repository or against the public site. Anything not checked is marked UNVERIFIED. Sources are numbered S1 to S23 at the end of section 3.

**Size: a small change.** One file of the page, a few tests, and steps added to the README's check by hand. No server code, no new dependency, no secret, no new paid call.

## 1. Why, and for whom

The assignment: "Include a chat interface to talk with the agent (voice is a bonus)" (`docs/ai-session/01-plan.txt`, line 139). It also says: "A narrow scope done well is better than a broad scope done shallowly." The owner asked for a design before anything is built, and set its scope: "Obviously the table can't be spoken. lets design spoken questions first" (2026-11-25). So this design covers speaking a question. Hearing an answer is outside it.

- **In the story,** an analyst asks the same questions as today, by voice instead of the keyboard. The answer is unchanged: a verdict, a table, and the data and confidence lines.
- **In reality,** the reviewers should be able to try the bonus alone, in their own browser, with nothing to set up but the microphone permission. The owner may show it in the interview.

One thing comes first. A typed question holds what the analyst typed. A spoken question holds what a speech recogniser heard. (Speech recognition is software that turns recorded speech into text.) MDN says mistakes happen most "with domain-specific terms (such as medical or scientific vocabulary), proper nouns, uncommon phrases, or words that sound similar to other words" (S2). Hub cities are proper nouns. One real hub heard as another gives a right-looking answer to the wrong question. So the design's main job is that the analyst sees the words and approves them before anything is sent.

The owner has not said why voice matters beyond the bonus. This design assumes the aim is a visible, honest bonus (section 8, question 3).

## 2. Goals, non-goals, anti-goals

Goals, most important first:

1. **A spoken question is sent only as the analyst approved it.** They see the words, can fix them, and press Ask themselves.
2. **The analyst knows where their voice goes** before they speak.
3. **Typing is untouched.** Whatever speech does or fails to do, the page works as it does today.
4. **A reviewer can try it alone** in a supported browser.
5. **Nothing else moves.** The API, the server, the agent and the evaluation are unchanged. No new paid call.

Non-goals: spoken answers (they may come later; the owner: the table cannot be spoken); voice commands such as "new conversation"; listening without a button press; languages other than English; phones; Firefox in this version (5.4); recognition that must stay on the device (section 8, question 1); a speech model or speech service of our own; marking a question as spoken in the conversation.

Anti-goals (a failure even if everything else works):

- A question reaches the agent that the analyst did not see and send.
- The page changes a recognised word by itself, for example to the nearest hub name. That would be a guess.
- Audio reaches our server, or we store any.
- The analyst is not told that the browser may send their voice to its maker.
- A browser without speech shows a broken control, or speech leaves Ask stuck.
- A test needs a paid call, a microphone or a driven browser.

## 3. Constraints

**The project** (checked in the code today):

- The page is one file of plain HTML, CSS and JavaScript with no packages (`src/wra/api/static/index.html`, 282 lines). A test refuses `src=`, `<link` and `import ` anywhere in it (`tests/test_api.py`, line 188), so a button icon cannot be an image file.
- The question box is `<textarea id="message" maxlength="2000">`. Two things send a question: the Ask button and the Enter key (lines 260 to 273). The submit handler already does nothing while Ask is disabled (line 263).
- The server refuses a message over 2,000 characters with HTTP 422 (`src/wra/api/app.py`, `MAX_MESSAGE`). MDN on `maxlength`: "Constraint validation is only applied when the value is changed by the user" (S16). So the browser does not hold text that a script writes into the box to 2,000.
- One test runs page code. It pulls `function boldOnly` out of the served page and runs it in Node, a program that runs JavaScript outside a browser, and it is skipped when Node is missing (`tests/test_api.py`, line 193). The rest of the page is checked by hand (README, "Checking the page by hand before a demo"). The owner chose that over a test against a stand-in page (`.claude/OPEN_ISSUES.md`, "The chat page").
- The public site is HTTPS, behind the browser's own sign-in box on every route but `/healthz` (`src/wra/api/public.py`).
- Measured: 418 tests pass (`uv run pytest -q` on `66a586a`).
- Project rules that bear on it: no paid call in a test (rule 12); say what we don't know (rule 5); never a guess (rules 2 and 8).

**The browsers.** The Web Speech API is a feature built into some browsers. A page asks the browser to listen, and the browser hands back text. The page never holds the audio.

| Question | What was read |
|---|---|
| Which browsers have it | Chrome from 33 under a prefixed name (`webkitSpeechRecognition`) and from 139 under the standard one. Edge is listed as mirroring Chrome. Safari from 14.1, prefixed name only. Firefox from 160 on desktop, released 2026-11-10, and not on Android. Current versions: Chrome 158, Edge 158, Safari 27.2, Firefox 160; Firefox's long-support version, 153, lacks it. (S3) |
| Where the audio goes, in general | "The browser decides where speech recognition is performed." (S2) The specification: with the default setting "user speech data might be sent to a remote server for processing", and browsers "are encouraged to be transparent with users about where speech processing occurs". (S4) |
| Chrome | "Audio is sent to Google's servers (upstream) and text is returned (downstream)." The request allows no cookies ("cookies_allowed: NO"). (S5, Chrome's own source code) From Chrome 139 a page can instead demand recognition on the device, after a one-time download (S3, S18). |
| Safari | "Safari supports speech recognition powered by the same speech engine as Siri." "Note that users will need Siri enabled in System Preferences on macOS". (S6) Apple on Siri and Dictation: "your device will indicate in Siri Settings or Keyboard Settings whether the things you say are processed on your device and not sent to Apple. Otherwise, the things you say are sent to and processed by Apple." (S7) Whether that page covers speech on a web page in Safari: UNVERIFIED. Safari has no switch to demand on-device recognition (S3). |
| Edge | Microsoft documents only a model on the device, "available in Microsoft Edge Canary or Dev (version 150.0.4076 or later)", behind a setting (S8). Where released Edge sends audio: UNVERIFIED. On Microsoft's own forum, users reported "network error" from this feature in Edge 147 from April 2026 (S9). Whether that is fixed: UNVERIFIED. |
| Firefox | "On-device speech recognition ... is now available on desktop ... Recognition is not supported on Android, and neither is remote (cloud) recognition." (S10) On-device recognition needs a language pack, the data a browser needs to recognise one language. The specification says a browser must treat a pack as not available until the page itself has asked to install it, and must then report `service-not-allowed` (S4). The install call needs a recent user action such as a click (S17). So a plain "start listening" is expected to fail in Firefox. How Firefox 160 really behaves: UNVERIFIED. |
| Consent | "User agents must only start speech input sessions with explicit, informed user consent." They "must give the user an obvious indication when audio is being recorded". (S4) Chrome: "The user must allow the browser to access the microphone in a permission prompt. This is set per site". (S5) The prompt offers "Allow while visiting the site, Allow this time, or Never allow". (S12) |
| HTTPS | The specification offers the feature only to pages on HTTPS or on this machine's own address (S4, S14: a host in "127.0.0.0/8" counts). Chrome: "Pages hosted on HTTPS do not need to ask repeatedly for permission, whereas HTTP hosted pages do." (S11) Whether Chrome remembers the permission for `http://127.0.0.1:8000`: UNVERIFIED. |
| A header that could block it | A server can send a `Permissions-Policy` header that switches browser features off for its pages. "The default allowlist for `microphone` is `self`" (S13), so with no such header our own page may ask. Measured: the public site's replies to `/healthz` and to `/` without sign-in carry no `Permissions-Policy` and no `Content-Security-Policy` header, and `src/` sets none (grep, 0 matches). The signed-in page's headers: UNVERIFIED; 5.6 shows it by hand. |
| How it fails | The browser reports a code: `not-allowed`, `service-not-allowed`, `network`, `no-speech`, `audio-capture`, `language-not-supported`, `aborted` (S15). Starting twice throws an error (S1). The `end` event "must always be generated when the session ends no matter the reason" (S4). |
| Words that may still change | An interim result is the recogniser's guess so far: it "may be updated later on" (S1). |

Sources:
S1 developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition (and its `start`, `continuous`, `interimResults`, `lang` and `SpeechRecognitionResult/isFinal` pages).
S2 developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API/Using_the_Web_Speech_API.
S3 github.com/mdn/browser-compat-data, `api/SpeechRecognition.json`, `api/MediaRecorder.json` and `browsers/` (the data behind MDN's support tables).
S4 webaudio.github.io/web-speech-api/ (Web Speech API, Draft Community Group Report, 27 October 2026).
S5 chromium.googlesource.com/chromium/src/+/main/content/browser/speech/network_speech_recognition_engine_impl.cc.
S6 webkit.org/blog/11648/new-webkit-features-in-safari-14-1/.
S7 www.apple.com/legal/privacy/data/en/ask-siri-dictation/.
S8 learn.microsoft.com/en-us/microsoft-edge/web-ai/speech-recognition-api.
S9 techcommunity.microsoft.com/discussions/edgeinsiderdiscussions/web-speech-api-not-working-in-edge-v-147/4514880 (a forum, not documentation).
S10 developer.mozilla.org/en-US/docs/Mozilla/Firefox/Releases/160.
S11 developer.chrome.com/blog/voice-driven-web-apps-introduction-to-the-web-speech-api.
S12 support.google.com/chrome/answer/2693767.
S13 developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Permissions-Policy/microphone.
S14 developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts.
S15 developer.mozilla.org/en-US/docs/Web/API/SpeechRecognitionErrorEvent/error.
S16 developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/maxlength.
S17 developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition/install_static.
S18 developer.chrome.com/release-notes/139.
S19 platform.claude.com/docs/en/about-claude/models/overview.
S20 developers.openai.com/api/docs/pricing.
S21 support.apple.com/guide/mac-help/use-dictation-mh40584/mac.
S22 support.microsoft.com/en-us/windows/use-voice-typing-to-talk-instead-of-type-on-your-pc-fec94565-c4bd-329d-e59a-af033fa5689f.
S23 developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia.

## 4. Approaches considered

**The owner picked A** (2026-11-25). The rest of this document follows it.

| | A. The browser's built-in recognition (recommended) | B. A speech-to-text service called from our server | C. Build nothing: the operating system's dictation |
|---|---|---|---|
| How | The page asks the browser to listen. Text lands in the question box. | The page records audio and uploads it to a new route. Our server sends it to a vendor and returns the text. | The analyst uses the computer's own dictation, which types into any text box. |
| Money per question | None. | One vendor's list price: "$0.0045 / minute" (S20). A ten-second question, an assumed length, would be about 0.075 cents if billed by the second (billing unit UNVERIFIED). That is the measured cost of one answer today (`docs/EVAL_RESULTS.md`), so a spoken question would cost about double. | None. |
| New keys or secrets | None. | One, at a second vendor. Claude takes no audio: "All current models support text and image input" (S19). Rule 7 names two secrets today; this adds a third at the host. | None. |
| Browsers | Chrome and Safari; Edge expected; Firefox not without more work (5.4). | Every current desktop browser: recording is in Chrome from 47, Firefox from 25 and Safari from 14.1 (S3), and needs HTTPS or this machine's own address (S23). | Any, in principle. Not tested here. |
| Where the audio goes | To the browser's maker, or it stays on the device: section 3. Never to our server. | Through our server to the vendor. | Apple: the Mac's Keyboard settings say whether speech is "processed on your device and not sent to Siri servers" (S21). Windows: "Voice typing uses online speech recognition, which is powered by Azure Speech services." (S22) |
| Tested without a paid call | Two small functions in Node, text checks on the page, the check by hand. | Server tests with a fake vendor. A real check is a paid call (rule 12). | Nothing to test. |
| To build | The page only. Small. | A project: a new route, a vendor client, upload limits, a spending guard beside the daily question limit, audio formats that differ by browser (UNVERIFIED). | A README line. |

**Recommended: A.** It costs nothing, needs no secret and no server change, adds no paid call to guard, and our server never sees audio. Its weak points are real: it does not work everywhere, in Chrome the audio goes to Google, and how well it hears is unknown until tried. The design states each of them on the page or in the README, and typing is always there.

**B** is the answer when every browser must work alike, or when a company must choose where its audio goes. At demo grade it buys that with a second vendor, a third secret and a new paid path on a public site. **C** is honest and free, but it is not a feature of the chat: a reviewer sees nothing built. Two more were dropped at once. A speech model inside the page needs a JavaScript package and a model file, which the "no JavaScript packages" rule excludes. A speech model on our own server would take the audio upload of B and a heavy new dependency, on an instance with 512 MB of which the server uses about 120 MB at rest (`docs/DEPLOY_DESIGN.md`, sections 3 and 9); whether any model fits was not measured.

## 5. The design

Everything in this section is Claude's call, for the owner to check.

### 5.1 The Speak button

- The form gains one button, **Speak**, beside Ask. The HTML carries it hidden. The script shows it only when the browser offers speech recognition under either name (`SpeechRecognition`, or the prefixed `webkitSpeechRecognition` that Safari uses). In any other browser the page is today's page.
- One press starts listening, and the button reads **Stop**. Listening ends when the analyst pauses, presses Stop, or the browser reports a problem. Then the button reads Speak again.
- Settings: English, set explicitly (`lang` "en-US"; MDN: "Setting this explicitly is the recommended best practice"). One utterance per press (`continuous` false: "at most one final result"). Words shown while they are heard (`interimResults` true). Where recognition runs is left to the browser (`processLocally` stays false).
- Pressing Stop puts the page back to normal at once, without waiting for the browser. So Ask can never stay stuck.
- A spoken question costs what a typed one costs. The speech step is free to us, and only Ask reaches the model.

### 5.2 Misheard words: seen, fixed, then sent

- **Seen.** The words go into the question box and nowhere else, and they appear while the analyst speaks. Text already in the box stays. The spoken words are added after it with one space. The result is cut at 2,000 characters, because the browser does not apply the box's limit to text a script writes (section 3).
- **Fixed.** When listening ends, the box is an ordinary text box again, with the cursor at the end. The analyst corrects a word by typing. Pressing Speak again adds more. While listening, the box is read-only, so the next result cannot overwrite a correction half made.
- **Then sent, by the analyst.** Speech never sends. Only Ask and Enter send, as today. While listening, Ask is disabled, and Enter then does nothing (line 263), so words the recogniser may still change cannot be sent. One trap: today `setWorking` alone sets Ask's state (line 219). The builder makes one rule, "disabled while working or listening". Otherwise an answer that arrives mid-speech re-enables Ask.
- **Never corrected by the page.** No matching against hub names. A wrong guess by our code would look as right as a wrong guess by the recogniser.
- **What already stands behind it.** The conversation shows the question exactly as sent. Code writes the tables, and they name their hubs. A city with no hub is answered "Out of scope" (evaluation case 11). None of that catches one real hub heard as another, which is why the analyst reads first.
- **Not used: word hints.** Browsers can take a list of likely phrases (`phrases`). Chrome has it from 142 and Safari not at all (S3), and a recogniser without it fails the whole request with `phrases-not-supported` (S4). It is the next step only if the owner's run in 5.6 shows hub names misheard.
- **How well it hears is unknown.** UNVERIFIED until the owner's run in 5.6. It depends on the speaker, the microphone and the room.

### 5.3 What the page tells the analyst

A fixed line under the box, shown whenever Speak is shown. The exact words are the builder's. It says three things:

1. The browser, not this site, turns the speech into text.
2. The browser may send the audio to its maker to do that. Chrome sends it to Google.
3. This site receives only the text, and only when Ask is pressed. Check the words first, hub names above all.

A second line, in the pattern of the page's "Working" line and announced to screen readers, says what is happening: listening; then "check the words, then press Ask"; or the problem from 5.4. The README repeats the three points browser by browser, with what is UNVERIFIED (section 3: Safari and Edge).

### 5.4 Browsers, and what happens where speech fails

| Browser | This version |
|---|---|
| Chrome, desktop | Supported. Checked by hand. Audio goes to Google. |
| Safari 14.1 or later | Supported when Siri is on. Checked by hand if the owner has a Mac. Audio stays on the device or goes to Apple, as the Mac's settings say (UNVERIFIED for web pages). |
| Edge | Expected to work, since it is listed as Chrome is. Not promised (section 3). |
| Firefox 160 or later | The button shows, and pressing it is expected to end in the plain message below (section 3). Making it work means a download step for the language pack. Not in this version (section 8, question 2). |
| Firefox before 160, any browser without the feature, a page served over plain HTTP from another machine | No button. The page is today's page. |

Having the feature is not proof that it works. So every failure ends the same way: the button reads Speak again, one plain line says what happened, and the box keeps whatever it held.

| The browser reports | The page says (wording is the builder's) |
|---|---|
| `not-allowed` | The microphone is blocked for this site. How to allow it, or type the question. |
| `service-not-allowed`, `language-not-supported` | This browser cannot recognise speech here. Type the question. |
| `network` | The browser could not reach its speech service. Type the question. |
| `no-speech` | Nothing was heard. Press Speak to try again. |
| `audio-capture` | No working microphone was found. |
| `aborted` | Nothing. |
| Anything else, or an error on starting | Speech stopped, with the code. Type the question. |

### 5.5 The microphone permission, the sign-in and the host

- **What the browser requires.** Consent, which it asks for in its own prompt the first time Speak is pressed. A page on HTTPS or on this machine's own address: the public site is HTTPS, and the local run is `http://127.0.0.1:8000`. The page starts listening only from the button's click, which meets any rule about a user action.
- **The sign-in cannot get in the way.** The page calls the browser, and the browser calls its own service or model. No request for speech goes to our server, so the sign-in has nothing to refuse. Chrome's request to Google carries no cookies (S5). This is reasoning from the sources; the check on the public site in 5.6 confirms it.
- **No header blocks it** on the replies measured (section 3). We add none.
- **Not checked from here:** whether the operating system also asks to let the browser use the microphone (UNVERIFIED), and whether Chrome asks again on every press on the local address (UNVERIFIED). Both show up in 5.6 and neither changes the design.

### 5.6 How it is checked

**By tests,** with no browser, no microphone and no model:

- Two functions written to stand alone, and run in Node as `boldOnly` is (skipped when Node is missing). The first joins the box's text and the heard words: an empty box, a box that does or does not end in a space, heard words that start with a space, no heard words, and the cut at 2,000. The second turns a failure code into the page's message: every code in 5.4's table, and an unknown one.
- The served page read as text, as `tests/test_container.py` reads `.dockerignore`. The Speak button is in the HTML and hidden. The notice's three points are there. The speech code sits between two marker comments, and nothing between them calls `ask(`, `requestSubmit`, `submit(`, `fetch(` or `click(`. Counted over the whole page: `ask(` appears twice (its definition and the one call in the submit handler), `requestSubmit` once and `fetch(` once, as today (lines 224, 265, 271, 229). The page holds no `getUserMedia` and no `MediaRecorder`, so it never has audio to upload.
- These prove the text, not the behaviour. The behaviour is checked by hand.

**By hand,** by the owner, as new steps in the README's check. Nothing drives the owner's browser. All of it is free except one spoken question, and none if step 1's question is spoken instead of typed.

1. Chrome, `uv run wra serve`, http://127.0.0.1:8000/. Speak and the notice line show. Press Speak. The browser asks for the microphone: allow it.
2. Say "Which hubs in the Midwest are most exposed to winter disruption?". The words appear in the box while you speak. The button reads Stop and Ask is greyed out. Pause. The button reads Speak, Ask is live, and nothing was sent: no question in the conversation, no "Working".
3. Change one word by typing. Press Speak again and add a few words: they follow the text already there. Press Ask: the answer arrives as usual.
4. The hub-name run. Say one short question for each of the twelve hub cities and each of the four hazards, sending none. Count how many came out with the hub or hazard wrong. The count goes in the README with the browser.
5. Block the microphone for the site in the browser's site settings and press Speak. The page says the microphone is blocked. Typing and Ask still work. Allow it again.
6. A browser without support, if one is at hand (Firefox). Either no button, or a plain message after pressing it. Typing works.
7. After the deploy, on the public site: sign in and repeat steps 1 and 2. This is the check that the sign-in and the host leave the microphone alone.
8. Safari, if at hand, with Siri on: steps 1 and 2.

The documents follow the build: the README (a line in the front door, the supported browsers, where the audio goes, the hub-name count, the new steps), ARCHITECTURE, one DECISIONS entry (the browser recognises, our server never receives audio, speech never sends), PLAN Deviations, ASSUMPTIONS and the chat page's entry in `.claude/OPEN_ISSUES.md`.

## 6. What only the owner does

1. Approve this design. (The approach and section 8's questions are answered.)
2. Run the check by hand in 5.6. The permission prompts are the owner's to answer.
3. Report the hub-name run's count. Voice ships whatever it is; above 2 of 16 wrong, the README says so and the notice leans harder on checking hub names (section 8, question 4).
4. Give the go for the push. The page ships inside the site's image, so this push must not carry `[skip render]`. It restarts the public site and resets open conversations (`CLAUDE.md`, Gotchas), so its moment is the owner's.
5. Before the interview, if voice will be shown live (not decided, section 8, question 5): say one question in the same setup as the call, since the call and the page share one microphone (how they behave together: UNVERIFIED). Typing is the fallback.

Nothing changes at Render or at Anthropic: no secret, no setting, no limit.

## 7. Left to the builder

Names and ids. The button's place, its look, and whether it carries an icon (inline only: the page test refuses `src=`). The exact words of the notice and of each message, keeping 5.3's three points. The two marker comments. How Ask's one rule is shared with `setWorking`. Whether words still changing look different in the box. Joining every result the browser returns, not only the first, since Safari before 17 returned several (S3). Whether "New conversation" stops listening. Test names. If the check by hand shows a dead button in Firefox, a way to hide it there.

If time runs short, cut in this order: words shown while speaking (show only the final words); the separate messages, down to two (microphone blocked, anything else). Never cut: speech never sends, Ask disabled while listening, the notice, and the tests of those three.

## 8. Questions for the owner, the owner's answers (2026-11-25), and Claude's calls

| # | Question | The owner's answer |
|---|---|---|
| 1 | In Chrome the analyst's voice goes to Google. Is telling them on the page enough, or must the audio stay on the device? ("Stay on the device" adds a one-time download step before first use, works only in Chrome 139 or later and Firefox 160 or later on desktop, and cannot be promised in Safari.) | **A notice is enough.** The notice of 5.3; recognition stays wherever the browser runs it. |
| 2 | Which browsers must it work in: the one for the demo, and should Firefox work? (Firefox means the same download step as question 1.) | **Firefox is left out of this version**, as 5.4 has it (the owner chose "a notice is enough" over "notice, and make Firefox work"). |
| 3 | Why voice, beyond the bonus? | Not stated. The design keeps its assumption: a visible, honest bonus. Analysts truly working by voice would put spoken answers and on-device recognition ahead of it. |
| 4 | What result of the hub-name run (5.6, step 4) decides it? | **More than 2 of 16 wrong: voice still ships, with a warning.** The README states the count and the browser, and the notice's third point leans harder on checking hub names. At 2 or fewer, the README states the count as usual. |
| 5 | Will voice be shown live in the interview, or left for reviewers to try? | **Not decided.** The rehearsal step in section 6 stays, marked optional. |

**Claude's calls, for the owner to check:** approach A; the words go to the question box and are never sent by speech; Ask disabled while listening; no correction of words by the page; the fixed notice with its three points; one utterance per press; English only; where recognition runs left to the browser; no word hints; Firefox left out of this version; no button where the feature is missing; text checks on the page instead of a stand-in page test; the hub-name run as the measure of how well it hears.
