"""The container image for the public site (docs/DEPLOY_DESIGN.md 5.6). What the image does is checked by
building and running it (docs/DEPLOY_PLAN.md, Task 3); this file guards what must never go into it."""

from conftest import REPO


def test_the_image_never_gets_the_secrets_or_the_transcripts():
    ignored = {line.strip() for line in (REPO / ".dockerignore").read_text().splitlines()}
    assert {".env", ".env.*", ".venv", ".git", "evals/runs", "docs/ai-session"} <= ignored
