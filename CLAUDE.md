@AGENTS.md

## Claude Code extras

These add to `AGENTS.md`. Other agents can ignore them.

- Hooks in `.claude/settings.json` enforce `AGENT_STOP`, surface `STEER.md` notes, and commit tracked changes when a session stops.
- Guides in `.claude/skills/` load as skills.
- Subagents in `.claude/agents/`: `lane-a-data`, `lane-b-planning`, `lane-c-ui`, `evaluator`, `integrator`.

## Orchestrator mode

One session runs all three lanes as subagents.

1. Start the three lane subagents in parallel, each in its own worktree on its lane branch (`isolation: worktree`).
2. Give each one the same instruction: "Continue from lanes/<lane>/PROGRESS.md."
3. Do not relay code between lanes. Lanes coordinate only through the files named in `AGENTS.md`.
4. When a lane reports done, run the `evaluator` subagent on that lane. On NEEDS_WORK, send the findings back to that lane.
5. Loop until the P0 items pass or the operator stops you. Use the `integrator` subagent to merge lanes.
