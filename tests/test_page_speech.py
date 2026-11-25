"""Spoken questions on the chat page (docs/VOICE_DESIGN.md, docs/VOICE_PLAN.md). The three speech functions run in
Node, as boldOnly's test does (tests/test_api.py); the rest of the speech code is read as text. No browser, no
microphone and no model call."""

import json
import re
import shutil
import subprocess

import pytest

from wra.api.app import MAX_MESSAGE, PAGE

BEGIN, END = "// SPEECH BEGIN", "// SPEECH END"
NO_NODE = "Node.js is not installed; the speech functions were checked by hand"


def page() -> str:
    """The file the server sends at /."""
    return PAGE.read_text(encoding="utf-8")


def speech_code() -> str:
    """The text between the two markers, where all the speech code sits."""
    text = page()
    return text[text.index(BEGIN) + len(BEGIN) : text.index(END)]


def run_in_node(functions: list[str], expression: str) -> object:
    """Pull each named function out of the page, run them in Node and return the expression's value."""
    text = page()
    code = []
    for name in functions:
        found = re.search(rf"^function {name}\(.*?^}}", text, re.M | re.S)
        assert found, f"function {name} not found in the page"
        code.append(found.group(0))
    node = shutil.which("node")
    if node is None:
        pytest.skip(NO_NODE)
    script = '"use strict";\n' + "\n".join(code) + f"\nconsole.log(JSON.stringify({expression}));"  # as the page
    run = subprocess.run([node, "-e", script], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def join_heard(cases: list, limit: int) -> list[str]:
    """joinHeard(text, parts, limit) for each [text, parts] case, in one Node run."""
    return run_in_node(["joinHeard"], f"{json.dumps(cases)}.map(([text, parts]) => joinHeard(text, parts, {limit}))")


# --- joining heard words to the box ----------------------------------------------------------


JOINED = [  # (the box's text when listening began, the transcript of every result so far, the box after)
    ("", ["Which hubs"], "Which hubs"),
    ("Which hubs", ["in the Midwest"], "Which hubs in the Midwest"),
    ("Which hubs ", ["in the Midwest"], "Which hubs in the Midwest"),
    ("Which hubs", [" in the Midwest"], "Which hubs in the Midwest"),
    ("", ["Which hubs", " in the Midwest"], "Which hubs in the Midwest"),  # two results: each word once
    ("Which hubs", [], "Which hubs"),
    ("Which hubs", ["", "  "], "Which hubs"),
    ("Which hubs\n", ["in the Midwest"], "Which hubs\nin the Midwest"),
]


def test_heard_words_join_the_text_already_in_the_box():
    assert join_heard([[text, parts] for text, parts, _ in JOINED], 2000) == [after for *_, after in JOINED]


def test_heard_words_are_cut_at_the_servers_limit():
    # A script's writes to the box are not held to its maxlength, and the server refuses a longer message
    assert join_heard([["x" * 1995, ["hello world"]], ["x" * 2000, ["more"]]], MAX_MESSAGE) == [
        "x" * 1995 + " hell", "x" * 2000]  # fmt: skip


# --- what the page says when speech fails ----------------------------------------------------


PROBLEMS = {
    "not-allowed": "The microphone is blocked for this site. Allow it in the browser's site settings, or type the question.",
    "service-not-allowed": "This browser cannot turn speech into text here. Type the question.",
    "language-not-supported": "This browser cannot turn speech into text here. Type the question.",
    "network": "The browser could not reach its speech service. Type the question.",
    "no-speech": "Nothing was heard. Press Speak to try again.",
    "audio-capture": "No working microphone was found. Type the question.",
    "aborted": "",
}  # fmt: skip


def test_every_speech_failure_has_its_plain_message():
    codes = json.dumps(list(PROBLEMS))
    assert run_in_node(["speechProblem"], f"Object.fromEntries({codes}.map((c) => [c, speechProblem(c)]))") == PROBLEMS


def test_an_unknown_speech_failure_names_its_code():
    assert run_in_node(["speechProblem"], 'speechProblem("bad-grammar")') == (
        "Speech stopped (bad-grammar). Type the question.")  # fmt: skip


# --- the guards on the page's script ---------------------------------------------------------


def test_the_speech_code_never_sends():
    text = page()
    for marker in (BEGIN, END):
        assert text.count(marker) == 1, marker
        assert marker in (line.strip() for line in text.splitlines()), f"{marker} is not on a line of its own"
    assert text.index(BEGIN) < text.index(END)
    code = speech_code()
    for call in ("ask(", "requestSubmit", "submit(", "fetch(", "click(", "dispatchEvent"):
        assert call not in code, call
    # As before speech: ask's declaration and the submit handler's call, Enter's requestSubmit, and ask's fetch
    assert (text.count("ask("), text.count("requestSubmit"), text.count("fetch(")) == (2, 1, 1)


def test_the_pages_script_parses(tmp_path):
    # A syntax error would stop the whole script, typing included (docs/VOICE_DESIGN.md, goal 3)
    scripts = re.findall(r"<script\b[^>]*>(.*?)</script>", page(), re.S)
    assert len(scripts) == 1
    node = shutil.which("node")
    if node is None:
        pytest.skip(NO_NODE)
    script = tmp_path / "page.js"
    script.write_text(scripts[0], encoding="utf-8")
    run = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr


# --- the Speak button, the notice and the status line ----------------------------------------


NOTICE = (
    "Speech is turned into text by your browser, not by this site. To do that, the browser may send your voice to "
    "its maker: Chrome sends it to Google. This site receives only the text, and only when you press Ask, so check "
    "the words first, especially hub names."
)


def test_the_speak_button_ships_hidden_and_never_submits():
    # type="button": a plain button inside the form, so pressing it never submits; the script shows it
    text = page()
    assert '<button id="speak" type="button" hidden>Speak</button>' in text
    assert '<p id="speech-notice" hidden>' in text
    assert '<p id="speech-status" role="status" hidden></p>' in text


def test_the_notice_says_where_the_voice_goes():
    assert NOTICE in " ".join(page().split())


def test_ask_follows_one_rule():
    # An answer arriving while listening must not re-enable Ask (docs/VOICE_DESIGN.md 5.2)
    text = page()
    assert text.count("send.disabled =") == 1
    assert "send.disabled = answering || listening;" in text
    assert "speak.disabled = on;" in text
    assert "send.disabled" not in speech_code()


def test_speech_follows_the_design():
    code = speech_code()
    for setting in ("window.SpeechRecognition || window.webkitSpeechRecognition", '.lang = "en-US"',
                    ".continuous = true", ".interimResults = true", "box.readOnly = true", "box.readOnly = false",
                    "joinHeard(spokenBase,", "box.maxLength", "Listening. Press Stop when you have finished.",
                    "tidySpoken(box.value, box.maxLength)"):  # fmt: skip
        assert setting in code, setting
    text = page()
    assert f'maxlength="{MAX_MESSAGE}"' in text  # the box's limit is the server's, so the cut matches it
    assert "processLocally" not in text and ".phrases" not in text  # left to the browser; no word hints


def test_the_page_never_holds_audio():
    # The browser turns speech into text; the page never has audio to upload
    text = page()
    assert "getUserMedia" not in text and "MediaRecorder" not in text


def test_listening_that_ends_by_itself_leaves_focus_on_speak():
    # When the browser ends listening while focus is on Speak, an Enter meant for Stop must not land in the box,
    # where it would send words the analyst has not read (docs/VOICE_DESIGN.md, the first anti-goal)
    assert "document.activeElement !== speak" in speech_code()


def test_late_events_and_stop_are_guarded():
    # One guard in each of the three handlers (result, error, end): a recognition that is no longer current is
    # ignored. Stop ends the browser's listening too, so its words cannot arrive later.
    code = speech_code()
    assert code.count("if (rec !== current) return;") == 3
    assert ".abort()" in code


# --- tidying the start and end of spoken words -----------------------------------------------


def tidy_spoken(texts: list[str], limit: int) -> list[str]:
    """tidySpoken(text, limit) for each text, in one Node run."""
    return run_in_node(["tidySpoken"], f"{json.dumps(texts)}.map((text) => tidySpoken(text, {limit}))")


TIDIED = [  # (the box when listening stopped, the box after); the words themselves never change
    ("which hubs are most exposed", "Which hubs are most exposed?"),
    ("What if a hurricane counted double", "What if a hurricane counted double?"),
    ("is Denver snowy", "Is Denver snowy?"),
    ("how", "How?"),
    ("compare Miami and Houston", "Compare Miami and Houston."),
    ("Which hubs are most exposed?", "Which hubs are most exposed?"),
    ("compare Miami and Houston.", "Compare Miami and Houston."),
    ("hello!", "Hello!"),
    ("why is Dallas high  ", "Why is Dallas high?"),
    ("3 hubs in the Midwest", "3 hubs in the Midwest."),
    ("", ""),
    ("   ", ""),
]


def test_spoken_words_are_tidied_at_the_start_and_end():
    assert tidy_spoken([text for text, _ in TIDIED], 2000) == [after for _, after in TIDIED]


def test_the_tidy_mark_respects_the_servers_limit():
    assert tidy_spoken(["x" * MAX_MESSAGE, "x" * (MAX_MESSAGE - 1)], MAX_MESSAGE) == [
        "X" + "x" * (MAX_MESSAGE - 1), "X" + "x" * (MAX_MESSAGE - 2) + "."]  # fmt: skip
