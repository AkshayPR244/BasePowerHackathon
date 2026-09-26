#!/usr/bin/env bash
# Session start for lanes/B-planning: sync main, install, check, show next items.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
LANE_DIR=lanes/B-planning
BRANCH=lane/b-planning
CHECK=check-b
PY=$(command -v python3 || command -v python)

if [ "$(git branch --show-current)" = "$BRANCH" ]; then
  git fetch origin && git merge --no-edit origin/main || echo "NOTE: could not merge origin/main. Resolve before new work."
fi

(cd backend && uv sync)

status=0
if [ -f Makefile ] && make -n "$CHECK" >/dev/null 2>&1; then
  make "$CHECK" || { status=$?; echo "CHECK FAILED: make $CHECK"; }
else
  echo "NOTE: make $CHECK does not exist yet. Running the fallback check."
  ( cd backend && if [ -d tests/lane_b ]; then uv run pytest -q tests/lane_b; else echo "NOTE: no lane B tests yet."; fi ) || { status=$?; echo "CHECK FAILED: fallback check"; }
fi

"$PY" - "$LANE_DIR/feature_list.json" <<'PY'
import json, sys
todo = [f for f in json.load(open(sys.argv[1])) if not f["passes"]]
print(f"{len(todo)} items not passing. Next:")
for f in todo[:3]:
    print(f"  {f['id']} [{f['priority']}] {f['title']}")
    print(f"      proof: {f['acceptance']}")
PY

exit $status
