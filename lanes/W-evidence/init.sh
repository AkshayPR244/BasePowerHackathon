#!/usr/bin/env bash
# Lane W-evidence session start: sync with main, install deps, run the lane check, list next items.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

if [ "$(git branch --show-current)" = "lane/W-evidence" ]; then
  git fetch origin && git merge --no-edit origin/main || echo "Merge from origin/main needs attention."
fi

if ! command -v uv >/dev/null 2>&1 && [ -n "${APPDATA:-}" ]; then
  scripts="$APPDATA/Python/Python314/Scripts"
  command -v cygpath >/dev/null 2>&1 && scripts="$(cygpath -u "$scripts")"
  export PATH="$scripts:$PATH"
fi

(cd backend && uv sync)
(cd frontend && pnpm install)

echo "== Lane check"
if [ -d backend/tests/lane_w ]; then
  (cd backend && uv run ruff check app/replay tests/lane_w && uv run pytest -q tests/lane_w tests/contract) || echo "Lane check failed. Fix it first."
else
  echo "No backend/tests/lane_w yet. Running contract tests."
  (cd backend && uv run pytest -q tests/contract) || echo "Checks failed. Fix them first."
fi
(cd frontend && pnpm typecheck) || echo "Frontend typecheck failed (season view)."

echo "== Next items"
python - "lanes/W-evidence/feature_list.json" <<'PY'
import json, sys
items = [i for i in json.load(open(sys.argv[1])) if not i["passes"]]
rank = {"P0": 0, "P1": 1, "P2": 2}
for i in sorted(items, key=lambda i: rank[i["priority"]])[:3]:
    print(f"{i['id']} [{i['priority']}] {i['title']}")
    print(f"    acceptance: {i['acceptance']}")
PY
