#!/usr/bin/env bash
# Lane R-engine session start: sync with main, install deps, run the lane check, list next items.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

if [ "$(git branch --show-current)" = "lane/R-engine" ]; then
  if ! { git fetch origin && git merge --no-edit origin/main; }; then
    echo "Sync with origin/main failed. Resolve the merge (or run 'git merge --abort'), then run init.sh again." >&2
    exit 1
  fi
fi

py=""
for c in python3 python; do "$c" -c "" 2>/dev/null && py="$c" && break; done

if ! command -v uv >/dev/null 2>&1 && [ -n "${APPDATA:-}" ]; then
  scripts="$APPDATA/Python/Python314/Scripts"
  command -v cygpath >/dev/null 2>&1 && scripts="$(cygpath -u "$scripts")"
  export PATH="$scripts:$PATH"
fi

(cd backend && uv sync)

echo "== Lane check"
if [ -d backend/tests/lane_r ]; then
  (cd backend && uv run ruff check app/recovery app/baselines app/planning tests/lane_r && uv run pytest -q tests/lane_r tests/lane_b tests/contract) || echo "Lane check failed. Fix it first."
else
  echo "No backend/tests/lane_r yet. Running lane_b and contract tests."
  (cd backend && uv run pytest -q tests/lane_b tests/contract) || echo "Checks failed. Fix them first."
fi

echo "== Next items"
[ -n "$py" ] || { echo "No python3 or python on PATH. Read lanes/R-engine/feature_list.json." >&2; exit 1; }
"$py" - "lanes/R-engine/feature_list.json" <<'PY'
import json, sys
items = [i for i in json.load(open(sys.argv[1], encoding="utf-8")) if not i["passes"]]
rank = {"P0": 0, "P1": 1, "P2": 2}
for i in sorted(items, key=lambda i: rank[i["priority"]])[:3]:
    print(f"{i['id']} [{i['priority']}] {i['title']}")
    print(f"    acceptance: {i['acceptance']}")
PY
