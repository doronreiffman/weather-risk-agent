#!/usr/bin/env python3
"""queue-guard.py — pre-commit hook: an open queue item leaves .claude/QUEUE.md only through Done / Dropped.

The queue is the ordered list of work for this project. Its one guarantee is that no item
is lost between sessions: a handoff may re-sort, add or move items, but every `[qN]` id
that is open in HEAD must still be present in the staged file, in any section. Ids under a
`## Done` / `## Dropped` heading in HEAD are history and may be pruned. Duplicate ids in
the staged file are refused too, so an id is never reused. A line under Done / Dropped must
say "Done <date>" or "dropped": the heading alone let an open item filed there by mistake
pass as finished (session 05, 2026-11-25).

WHY compare HEAD against the index rather than scan added lines: the failure this guards
against is an omission, and omissions leave no added line to scan.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass

QUEUE_PATH = ".claude/QUEUE.md"
ID_PATTERN = re.compile(r"^\s*-\s*\[q(\d+)\]")
HEADING_PATTERN = re.compile(r"^##\s+(.*)$")
CLOSED_PATTERN = re.compile(r"\b(done \d{4}-\d{2}-\d{2}|dropped)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Item:
    id: int
    is_open: bool  # False under a Done / Dropped heading
    text: str


def parse_items(text: str) -> list[Item]:
    """Every `- [qN]` line in order, tagged open or not by the `##` heading above it."""
    items: list[Item] = []
    is_open = True
    for line in text.splitlines():
        heading = HEADING_PATTERN.match(line)
        if heading:
            title = heading.group(1).lower()
            is_open = "done" not in title and "dropped" not in title
            continue
        m = ID_PATTERN.match(line)
        if m:
            items.append(Item(id=int(m.group(1)), is_open=is_open, text=line.strip()))
    return items


def check(head_text: str, staged_text: str) -> list[str]:
    """Problems that must block the commit; empty when the staged queue is acceptable."""
    head_items = parse_items(head_text)
    staged_items = parse_items(staged_text)
    staged_ids = Counter(item.id for item in staged_items)

    problems: list[str] = []
    for item_id, count in sorted(staged_ids.items()):
        if count > 1:
            problems.append(f"[q{item_id}] appears {count} times; ids are never reused")
    for item in staged_items:
        if not item.is_open and not CLOSED_PATTERN.search(item.text):
            problems.append(
                f"[q{item.id}] sits under Done / Dropped without 'Done <date>' or 'dropped': {item.text}\n"
                f"      if it is still open, move it back under '## Queue'"
            )
    for item in head_items:
        if item.is_open and item.id not in staged_ids:
            problems.append(
                f"[q{item.id}] vanished from the queue: {item.text}\n"
                f"      move it under '## Done / Dropped' with the date and where the proof is"
            )
    return problems


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], capture_output=True, text=True, errors="replace")


def main() -> int:
    staged_files = _git("diff", "--cached", "--name-only").stdout.splitlines()
    if QUEUE_PATH not in staged_files:
        return 0

    staged = _git("show", f":{QUEUE_PATH}")
    if staged.returncode != 0:
        return 0  # the queue file is being deleted; that is a deliberate act, not an omission
    head = _git("show", f"HEAD:{QUEUE_PATH}")
    head_text = head.stdout if head.returncode == 0 else ""  # first commit of the file

    problems = check(head_text, staged.stdout)
    if problems:
        print(f"\nqueue-guard BLOCKED: {QUEUE_PATH} would lose work.\n")
        for problem in problems:
            print(f"  {problem}")
        print("\nAn open item leaves the queue only through Done / Dropped. Fix the file and re-stage.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
