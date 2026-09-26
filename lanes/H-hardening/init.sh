#!/usr/bin/env bash
# Lane H-hardening session start: sync with main, install deps, run the lane check, list next items.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

if [ "$(git branch --show-current)" = "lane/H-hardening" ]; then
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
if [ -d backend/tests/lane_h ]; then
  (cd backend && uv run pytest -q tests/lane_h tests/contract) || echo "Backend lane check failed. Fix it first."
else
  echo "No backend/tests/lane_h yet. H-01 creates it."
  (cd backend && uv run pytest -q tests/contract) || echo "Contract tests failed. Fix them first."
fi
(cd frontend && pnpm typecheck && pnpm test) || echo "Frontend check failed. H-04 fixes the known stale test."

echo "== Next items"
python - "lanes/H-hardening/feature_list.json" <<'PY'
import json, sys
items = [i for i in json.load(open(sys.argv[1])) if not i["passes"]]
rank = {"P0": 0, "P1": 1, "P2": 2}
for i in sorted(items, key=lambda i: rank[i["priority"]])[:3]:
    print(f"{i['id']} [{i['priority']}] {i['title']}")
    print(f"    acceptance: {i['acceptance']}")
PY
