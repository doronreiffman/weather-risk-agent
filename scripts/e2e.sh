#!/usr/bin/env bash
# The final end-to-end check (docs/PLAN.md section 13, "Final end-to-end check").
#
#   scripts/e2e.sh          steps 1 to 3: clone, install, build the database offline, run the tests. Free.
#   scripts/e2e.sh --paid   also steps 4 to 6: six questions through the HTTP API, then `wra eval --reps 3`
#                           against the plan's target. These spend API credit: the owner approves each run.
#
# It checks the last commit, not the working copy: uncommitted changes are not in the clone.
set -euo pipefail

paid=false
case "${1:-}" in
  "") ;;
  --paid) paid=true ;;
  *) echo "usage: scripts/e2e.sh [--paid]" >&2; exit 2 ;;
esac

repo="$(cd "$(dirname "$0")/.." && pwd)"
port="${WRA_E2E_PORT:-8765}"
work="$(mktemp -d)"
server=""

finish() {
  local status=$?
  if [ -n "$server" ]; then
    kill "$server" 2>/dev/null || true
    wait "$server" 2>/dev/null || true
  fi
  if [ "$status" -ne 0 ] && [ -f "$work/server.log" ]; then
    printf '\nServer log, last 30 lines:\n'
    tail -n 30 "$work/server.log"
  fi
  rm -rf "$work"
  if [ "$status" -eq 0 ]; then printf '\nEnd-to-end check: PASSED\n'; else printf '\nEnd-to-end check: FAILED (exit %s)\n' "$status"; fi
}
trap finish EXIT

step() { printf '\n== %s\n' "$1"; }

step "1. Clone the last commit into a temporary folder"
git clone --quiet "$repo" "$work/repo"
cd "$work/repo"
git log --oneline -1
# The clone has no .env. Its app reads the original's through WRA_ENV_FILE; the key is never copied or printed.
export WRA_ENV_FILE="$repo/.env"

step "2. Install, then build the database from the committed raw responses (no network)"
uv sync --quiet
uv run wra ingest

step "3. Tests"
uv run pytest -q

if [ "$paid" != true ]; then
  step "Steps 4 to 6 skipped: they spend API credit. Run with --paid once the owner approves."
  exit 0
fi

if [ ! -f "$WRA_ENV_FILE" ]; then
  echo "error: no .env in $repo; the paid steps need ANTHROPIC_API_KEY there" >&2
  exit 1
fi
if curl --silent --max-time 2 "http://127.0.0.1:$port/healthz" > /dev/null; then
  echo "error: something already answers on port $port; set WRA_E2E_PORT to a free port" >&2
  exit 1
fi

step "4 and 5. Six questions through the HTTP API: schema, expected status, and the follow-up's context"
uv run wra serve --port "$port" > "$work/server.log" 2>&1 &
server=$!
uv run python -m wra.evals.e2e "http://127.0.0.1:$port"

step "6. The evaluation, three repetitions, against the plan's target"
eval_status=0
uv run wra eval --reps 3 --require-target || eval_status=$?
mkdir -p "$repo/evals/runs"
cp -R evals/runs/. "$repo/evals/runs/"  # keep the run record in the original repository; git ignores it
exit "$eval_status"
