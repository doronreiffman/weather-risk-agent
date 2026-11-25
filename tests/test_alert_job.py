"""The weekly score-change job on GitHub (docs/ALERT_DESIGN.md 5.4). What it does is checked by real runs on GitHub
(design section 6); this file guards what it may do, reading the workflow as text, as tests/test_container.py
reads .dockerignore."""

import re

from conftest import REPO

WORKFLOW = REPO / ".github" / "workflows" / "score-alert.yml"
DEMO = "github.event_name == 'workflow_dispatch' && inputs.demo"


def _steps(text: str) -> list[str]:
    return re.split(r"\n\s+- (?=name:|uses:)", text)


def test_the_alert_job_can_open_issues_and_nothing_more():
    text = WORKFLOW.read_text()
    block = re.search(r"^permissions:\n((?:[ ]+\S.*\n)+)", text, re.M)
    assert block, "no top-level permissions block"
    assert {line.strip() for line in block.group(1).splitlines()} == {"contents: read", "issues: write"}
    assert text.count("permissions:") == 1
    assert "git push" not in text and "contents: write" not in text


def test_the_alert_job_only_demos_on_a_manual_run():
    text = WORKFLOW.read_text()
    demo_lines = [line for line in text.splitlines() if "inputs.demo" in line]
    assert demo_lines
    assert all(DEMO in line for line in demo_lines), "a demo must also be a manual run"
    fetch = [step for step in _steps(text) if "wra ingest --refresh" in step]
    assert len(fetch) == 1
    assert f"if: ${{{{ !({DEMO}) }}}}" in fetch[0]


def test_the_alert_job_keeps_demo_and_real_issues_apart():
    text = WORKFLOW.read_text()
    assert "'score-change-demo'" in text and "'score-change'" in text
    assert "--assignee" in text


def test_the_duplicate_check_cannot_hide_a_failed_lookup():
    """Without `shell: bash` GitHub runs `bash -e`, with no pipefail, so `gh issue list ... | head` failing would read
    as "no issue open" and open a second one (whole-branch review, 2026-11-25)."""
    issue_step = next(step for step in _steps(WORKFLOW.read_text()) if "gh issue create" in step)
    assert re.search(r"^\s*shell: bash$", issue_step, re.M)
    assert "| head" not in issue_step
