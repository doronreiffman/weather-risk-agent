"""The pre-commit queue guard (.claude/hooks/queue-guard.py): what it refuses and what it lets through."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Loaded by path: the hyphen in the file name rules out an import. Registered first, because a dataclass
# looks its module up in sys.modules.
_spec = importlib.util.spec_from_file_location("queue_guard", ROOT / ".claude/hooks/queue-guard.py")
guard = importlib.util.module_from_spec(_spec)
sys.modules["queue_guard"] = guard
_spec.loader.exec_module(guard)


def queue(open_lines: list[str], closed_lines: list[str]) -> str:
    return "\n".join(["# Work queue", "", "## Queue", "", *open_lines, "", "## Done / Dropped", "", *closed_lines, ""])


def test_moving_an_item_to_done_with_its_date_passes():
    head = queue(["- [q1] Build the thing."], [])
    staged = queue([], ["- [q1] Build the thing. Done 2026-11-25. Proof: commit `abc1234`."])
    assert guard.check(head, staged) == []


def test_a_dropped_item_passes():
    head = queue(["- [q1] Build the thing."], [])
    staged = queue([], ["- [q1] Build the thing: dropped on the owner's word, 2026-11-25."])
    assert guard.check(head, staged) == []


def test_an_open_item_filed_under_done_is_refused():
    # Session 05: an open item landed under Done / Dropped and the guard, reading only the heading, let it through.
    head = queue(["- [q1] Build the thing."], [])
    staged = queue([], ["- [q1] Build the thing."])
    problems = guard.check(head, staged)
    assert len(problems) == 1
    assert "[q1]" in problems[0]
    assert "Done <date>" in problems[0]


def test_done_without_a_date_is_refused():
    staged = queue([], ["- [q1] Build the thing. Done."])
    assert len(guard.check(staged, staged)) == 1


def test_open_items_need_no_date():
    staged = queue(["- [q1] Build the thing.", "- [q2] Then the other thing."], [])
    assert guard.check(staged, staged) == []


def test_a_vanished_open_item_is_still_refused():
    head = queue(["- [q1] Build the thing."], [])
    problems = guard.check(head, queue([], []))
    assert len(problems) == 1
    assert "vanished" in problems[0]


def test_this_repositorys_queue_passes():
    text = (ROOT / ".claude/QUEUE.md").read_text()
    assert guard.check(text, text) == []
