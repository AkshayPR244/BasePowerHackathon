#!/usr/bin/env bash
# Lane C-canvas session start: sync with main, install deps, run the lane check, list next items.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

if [ "$(git branch --show-current)" = "lane/C-canvas" ]; then
  git fetch origin && git merge --no-edit origin/main || echo "Merge from origin/main needs attention."
fi

if ! command -v uv >/dev/null 2>&1 && [ -n "${APPDATA:-}" ]; then
  scripts="$APPDATA/Python/Python314/Scripts"
  command -v cygpath >/dev/null 2>&1 && scripts="$(cygpath -u "$scripts")"
  export PATH="$scripts:$PATH"
fi

(cd frontend && pnpm install)

echo "== Lane check"
(cd frontend && pnpm typecheck && pnpm test && pnpm build) || echo "Lane check failed. Fix it first."

echo "== Next items"
python - "lanes/C-canvas/feature_list.json" <<'PY'
import json, sys
items = [i for i in json.load(open(sys.argv[1])) if not i["passes"]]
rank = {"P0": 0, "P1": 1, "P2": 2}
for i in sorted(items, key=lambda i: rank[i["priority"]])[:3]:
    print(f"{i['id']} [{i['priority']}] {i['title']}")
    print(f"    acceptance: {i['acceptance']}")
PY
