#!/usr/bin/env bash
# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
#
# Commit tracked changes at the end of every session so work is durable across
# restarts. Stages tracked files only: new source files are the agent's job
# (`git add`, per CLAUDE.md). Skips main, master, and a detached HEAD, and never
# stages the e2e screenshots, which change on every Playwright run.
#
# Fails silently if commit can't be made (no git user.name, hook rejects, etc);
# check `git log` periodically when relying on this as a backstop.
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
case "$(git branch --show-current 2>/dev/null)" in
  "" | main | master) exit 0 ;;
esac
top="$(git rev-parse --show-toplevel)"
git -C "$top" add -u -- . ':(exclude)frontend/e2e/screenshots' >/dev/null 2>&1
if ! git -C "$top" diff --cached --quiet; then
  git -C "$top" commit -m "session checkpoint: $(date '+%Y-%m-%d %H:%M')" >/dev/null 2>&1
fi
exit 0
