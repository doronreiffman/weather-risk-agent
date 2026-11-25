"""Spoken questions on the chat page (docs/VOICE_DESIGN.md, docs/VOICE_PLAN.md). The two speech functions run in
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
