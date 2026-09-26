# Rollout Planner

A planning and recovery analysis tool for residential battery installers. Input: an installation plan plus a disruption. Output: the best recovery, the commitments at risk, and why. It is not booking or appointment-picking. Use these words everywhere: plan, disruption, recovery, commitments, risk, impact, explanation.

Hackathon build. About 40 hours. Three lanes build in parallel. Spec: `docs/SPEC.md`. Decisions: `docs/DECISIONS.md`.

## Priorities

1. Vertical slice first. The tiny fixture must flow data → solver → validator → API → UI before anything gets deeper.
2. 80/20. Ship the version that is 80% as good for 20% of the effort. Do not polish what does not work end to end.
3. Never block on real data, the network, or another lane. Use a labeled synthetic fixture or a recorded mock and continue.
4. Every plan shown anywhere passes the independent validator. Correctness beats features.
5. Small commits with clear messages. Update your lane's `PROGRESS.md` after every feature.
6. If an item takes more than 45 minutes without progress, write the blocker to `PROGRESS.md`, cut scope, and go to the next item.
7. Label synthetic, modeled, and assumed data as such in data, UI, and docs. Never claim a result we did not measure.

## Lanes

| Lane | Branch | Owns | Must not edit |
|---|---|---|---|
| A · Data, valuation, truth | `lane/a-data` | `backend/app/{data,valuation,validate}`, `backend/tests/{lane_a,contract}`, `data/` except `data/demo/tiny/expected/` | planning, api, frontend |
| B · Planning and API | `lane/b-planning` | `backend/app/{planning,baselines,compare,api}`, `backend/tests/lane_b`, `scripts/{export_openapi,record_mocks}.py`, `contracts/openapi.json`, `frontend/src/mocks/recorded/` | data, valuation, validate, frontend source |
| C · UI | `lane/c-ui` | `frontend/` except `src/api/generated.ts` and `src/mocks/recorded/`, `scripts/gen_types.sh` | backend, data |

Shared and frozen: `backend/app/contracts/` and the generated files `contracts/openapi.json` and `frontend/src/api/generated.ts`. Change them only through `docs/CONTRACTS.md`. The tiny expected results in `data/demo/tiny/expected/` are ground truth. Do not edit them to make a test pass.
Each lane's full brief: `lanes/<lane>/BRIEF.md`. Its checklist: `lanes/<lane>/feature_list.json`.

## Session start ritual

1. `pwd` and `git branch --show-current`. Confirm you are on your lane branch.
2. `git log --oneline -10`.
3. Read `lanes/<lane>/PROGRESS.md`, then `lanes/<lane>/feature_list.json`, then any `lanes/*/NEEDS.md` addressed to you.
4. Run `lanes/<lane>/init.sh`. It merges `origin/main`, installs deps, and runs the lane check.
5. If the check fails, fix that first.
6. Pick the highest-priority item with `"passes": false`. Work on one item at a time.

## Done means

- The item's `acceptance` command passes, or its evidence file exists and you opened it.
- `make check-<lane>` passes.
- Then set `"passes": true`, update `PROGRESS.md`, and commit.

## Commits and merges

- Commit small, on your lane branch, with an imperative message: `lane-a: validator checks inventory by day`.
- `git add` new files yourself. The Stop hook commits only tracked changes.
- When a P0 item lands and the lane check passes, push the lane branch and open a PR to `main` with `gh pr create`. A human merges it. Integrate early, not only in the morning.
- Never push to `main`. Never force-push. Never merge your own PR.

## Coordination (files only)

- `lanes/<lane>/PROGRESS.md`: handoff note. Done, In progress, Next, Blockers.
- `lanes/<lane>/NEEDS.md`: requests to another lane. Name the lane, the need, and what you use until then.
- `contracts/CHANGE_REQUESTS.md`: contract changes. See `docs/CONTRACTS.md`.

## Operator controls

- `touch AGENT_STOP` at the repo root halts every tool call. Remove the file to resume.
- Write to `STEER.md` (all agents) or `lanes/<lane>/STEER.md` (one lane) to redirect a running agent. The hook shows it once and clears it.

## Orchestrator mode

One session runs all three lanes as subagents: `lane-a-data`, `lane-b-planning`, `lane-c-ui` (`.claude/agents/`).

1. Start the three subagents in parallel, each in its own worktree on its lane branch (`isolation: worktree`).
2. Give each one instruction: follow the session start ritual and finish the next feature-list item.
3. Do not relay code between lanes. Lanes coordinate only through the files above.
4. When a lane reports done, run the `evaluator` subagent on that lane. On NEEDS_WORK, send the findings back to that lane.
5. Loop until the P0 items pass or the operator stops you. Use the `integrator` subagent to merge lanes.

## Writing

Use the `plain-english` skill for UI copy, docs, commits, and explanations. Short sentences. Concrete numbers. Name the cause.
