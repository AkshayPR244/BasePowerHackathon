#!/usr/bin/env bash
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
# Adapted: per-lane STEER files and a python fallback for systems without python3.
# If a STEER file has content, surface it to the agent once and clear the file.
# lanes/<lane>/STEER.md targets one lane. ./STEER.md targets every agent.
# This is a convenience channel, not a trust boundary.
root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
py=""
for c in python3 python; do "$c" -c "" 2>/dev/null && py="$c" && break; done
[ -n "$py" ] || exit 0
input="$(cat)"

agent=$(printf '%s' "$input" | "$py" -c 'import json,sys; d=json.load(sys.stdin); print(d.get("agent_type") or "")' 2>/dev/null)
branch=$(git -C "$root" branch --show-current 2>/dev/null)
case "$agent:$branch" in
  *:lane/R-engine) lane_file="$root/lanes/R-engine/STEER.md" ;;
  *:lane/C-canvas) lane_file="$root/lanes/C-canvas/STEER.md" ;;
  *:lane/W-evidence) lane_file="$root/lanes/W-evidence/STEER.md" ;;
  *) lane_file="" ;;
esac

for f in $lane_file "${AGENT_STEER_FILE:-$root/STEER.md}"; do
  if [ -s "$f" ]; then
    reason=$("$py" -c 'import json,sys; print(json.dumps("OPERATOR STEERING: " + sys.argv[1] + "\n\nPause what you were about to do, incorporate this guidance, then continue toward the feature goal."))' "$(cat "$f")") || exit 0
    printf '{"decision":"block","reason":%s}\n' "$reason"
    : > "$f"
    exit 0
  fi
done
