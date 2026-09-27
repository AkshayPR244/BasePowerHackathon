#!/usr/bin/env bash
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
# Halt every tool call while AGENT_STOP exists. `touch AGENT_STOP` to engage; `rm AGENT_STOP` to resume.
# Checks the worktree and the main checkout, so one file at the main repo root stops agents in every worktree.
top="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
main="${common:+$(dirname "$common")}"
for f in ${AGENT_STOP_FILE:+"$AGENT_STOP_FILE"} "$top/AGENT_STOP" ${main:+"$main/AGENT_STOP"}; do
  if [ -e "$f" ]; then
    cat <<'JSON'
{"decision":"block","reason":"Kill switch engaged: AGENT_STOP file exists. Agent is halted. Remove the file to resume."}
JSON
    exit 0
  fi
done
exit 0
