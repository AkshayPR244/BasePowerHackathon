#!/usr/bin/env bash
# Lane H-hardening session start: sync with main, install deps, run the lane check, list next items.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

if [ "$(git branch --show-current)" = "lane/H-hardening" ]; then
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
(cd frontend && pnpm install)

echo "== Lane check"
if [ -d backend/tests/lane_h ]; then
  (cd backend && uv run pytest -q tests/lane_h tests/contract) || echo "Backend lane check failed. Fix it first."
else
  echo "No backend/tests/lane_h yet. H-01 creates it."
  (cd backend && uv run pytest -q tests/contract) || echo "Contract tests failed. Fix them first."
fi
(cd frontend && pnpm typecheck && pnpm test) || echo "Frontend check failed. Fix it first."

echo "== Next items"
[ -n "$py" ] || { echo "No python3 or python on PATH. Read lanes/H-hardening/feature_list.json." >&2; exit 1; }
"$py" - "lanes/H-hardening/feature_list.json" <<'PY'
import json, sys
items = [i for i in json.load(open(sys.argv[1], encoding="utf-8")) if not i["passes"]]
rank = {"P0": 0, "P1": 1, "P2": 2}
for i in sorted(items, key=lambda i: rank[i["priority"]])[:3]:
    print(f"{i['id']} [{i['priority']}] {i['title']}")
    print(f"    acceptance: {i['acceptance']}")
PY
