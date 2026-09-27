#!/usr/bin/env bash
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
# Adapted: per-lane STEER files, worktree support, and a python fallback for systems without python3.
# Surface each STEER note once per session. lanes/<lane>/STEER.md targets one lane. ./STEER.md targets every agent.
# The hook never empties a STEER file: every agent must see the note. Seen state lives in the git dir, per session.
# This is a convenience channel, not a trust boundary.
top="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
main="${common:+$(dirname "$common")}"
py=""
for c in python3 python; do "$c" -c "" 2>/dev/null && py="$c" && break; done
[ -n "$py" ] || exit 0
input="$(cat)"

session=$(printf '%s' "$input" | "$py" -c 'import json,sys; d=json.load(sys.stdin); print(d.get("session_id") or "")' 2>/dev/null)
branch=$(git -C "$top" branch --show-current 2>/dev/null)
case "$branch" in
  lane/R* | fix/R*) lane=R-engine ;;
  lane/C* | fix/C*) lane=C-canvas ;;
  lane/H* | fix/H*) lane=H-hardening ;;
  *) lane="" ;;
esac

files=()
for r in "$top" ${main:+"$main"}; do
  [ -n "$lane" ] && files+=("$r/lanes/$lane/STEER.md")
done
if [ -n "${AGENT_STEER_FILE:-}" ]; then
  files+=("$AGENT_STEER_FILE")
else
  for r in "$top" ${main:+"$main"}; do files+=("$r/STEER.md"); done
fi

seen_dir="${common:-${TMPDIR:-/tmp}}/steer-seen"
seen="$seen_dir/${session:-no-session}"
mkdir -p "$seen_dir" 2>/dev/null

for f in "${files[@]}"; do
  [ -s "$f" ] || continue
  key="$f $(cksum < "$f")"
  grep -Fqx -- "$key" "$seen" 2>/dev/null && continue
  reason=$("$py" -c 'import json,sys; print(json.dumps("OPERATOR STEERING: " + sys.argv[1] + "\n\nPause what you were about to do, incorporate this guidance, then continue toward the feature goal."))' "$(cat "$f")") || exit 0
  printf '%s\n' "$key" >> "$seen" 2>/dev/null
  printf '{"decision":"block","reason":%s}\n' "$reason"
  exit 0
done
exit 0
