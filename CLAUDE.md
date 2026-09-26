@AGENTS.md

## Product (read first)

Rollout Planner is a deterministic disruption-recovery planner for installation operations. It shows what broke, how the disruption cascades through the current plan, what feasible recovery actions exist, what each costs or saves relative to doing nothing, and lets the operations manager review, test changes, and approve. R is the product, C is the experience, H makes it demo-safe. Weather replay is a parked nice-to-have (`lanes/_parked/weather`).

**Flow:** current plan → known disruption → impact analysis → recovery options (no action, rebalance, overtime, temporary capacity) → solve + validate each → economic and operational comparison → human review (inspect, pin, drag, test) → approve → updated plan.

**Vocabulary**
- "Install" is the electrical disconnect visit. "Battery day" is the battery placement visit.
- Say "customers to reschedule". Never say "changed installs".
- Options are business actions, such as "Crew IB +2h overtime". Never "Plan 3".
- The cheapest option is labeled "Lowest modeled cost". Never "Recommended".

**Weather wording** (applies only if weather returns from `lanes/_parked/weather`): "This replay applies a modeled operational disruption to a real historical storm." Never imply a storm actually stopped any company's crews.

**Out of scope:** routing, intra-day job order, travel miles, storm movement on a map, forecasting, probabilities, stochastic optimization, live feeds or APIs, autonomous approval, LLM explanations, chat UI.

## Lanes (today)

| Lane | Branch | Mission |
|---|---|---|
| R-engine | `lane/R-engine` | The recovery engine: impact, options, economics, evaluate, approve |
| C-canvas | `lane/C-canvas` | The Recovery Canvas: disruption bar, cascade, plan lanes, option cards, approve |
| H-hardening | `lane/H-hardening` | Demo-safe and trustworthy: live API wiring, error, stub, and validation honesty, e2e, accessibility, freeze script, demo docs |

Launch a lane: `git switch lane/R-engine` (or `lane/C-canvas`, `lane/H-hardening`), then tell the agent: "Read AGENTS.md and CLAUDE.md, then lanes/R-engine/PROGRESS.md, and continue from there."

Old lanes A, B, and C live in `lanes/_archive/`. Weather is a parked nice-to-have in `lanes/_parked/weather`. Revisit it when R-engine and C-canvas P0 items pass.

## Workflow (today's build)

**Session start ritual**
1. `pwd`, then `git log --oneline -10`.
2. Read your lane's `BRIEF.md`, `PROGRESS.md`, and `feature_list.json`.
3. Run `lanes/<lane>/init.sh`. It merges `origin/main`, installs deps, and runs the lane check.
4. Run a smoke test: `cd backend && uv run pytest -q tests/contract` (C: `cd frontend && pnpm typecheck`).
5. Pick the highest-priority item with `"passes": false`.

**Rules**
- Edit only your lane's owned paths.
- Contract changes are additive only. Log each one in `contracts/CHANGE_REQUESTS.md`.
- Generated files that conflict get regenerated, never hand-merged: `contracts/openapi.json`, `frontend/src/api/generated.ts`, `frontend/src/mocks/recorded/*`. Use `make types` and `make mocks`.
- Every plan the UI can show passes the independent validator.
- Every new number has a source or the tag "assumed" with a one-line reason. Nothing comes from any company's internal data.
- One PR per `feature_list.json` item. Merge only after `make check-contracts`, `make check-a`, `make check-b`, and the frontend checks (`cd frontend && pnpm typecheck && pnpm test && pnpm build`) pass and the `evaluator` subagent returns PASS.
- Update `PROGRESS.md` after every item.
- If an item stalls for 45 minutes, write the blocker in `PROGRESS.md`, cut scope, and move on.
- Never push to `main`. Never force-push.

**Timeline**
- Hour 0: seams frozen (this scaffold).
- Hours 1 to 4: build on recorded mocks and stubs.
- Hour 4 sync: Lane C swaps one flow to the live API. Lane H runs the live e2e.
- Hours 4 to 8: finish P0, push P1.
- Then a 2-hour joint integration: merge R, then H, then C. Run the full flow on the storm case. Run the freeze script. Record the demo.
- During sleep, agents open PRs only and never merge.

## Claude Code extras

These add to `AGENTS.md`. Other agents can ignore them.

- Hooks in `.claude/settings.json` enforce `AGENT_STOP`, surface `STEER.md` notes, and commit tracked changes when a session stops.
- Guides in `.claude/skills/` load as skills.
- Subagents in `.claude/agents/`: `evaluator` and `integrator`. The day 1 lane subagents were removed; they are in git history.

## Orchestrator mode

One session can run all three lanes with generic subagents.

1. Start one subagent per lane, each in its own worktree on its lane branch (`isolation: worktree`).
2. Give each one the same instruction: "Read AGENTS.md and CLAUDE.md. Continue from lanes/<lane>/PROGRESS.md."
3. Do not relay code between lanes. Lanes coordinate only through the files named in `AGENTS.md`.
4. When a lane reports an item done, run the `evaluator` subagent on it. On NEEDS_WORK, send the findings back to that lane.
5. Loop until the P0 items pass or the operator stops you. Merge in the order R, H, C.
