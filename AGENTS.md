# Rollout Planner · agent rules

Rollout Planner is a deterministic disruption-recovery planner for installation operations. It shows what broke, how the disruption cascades through the current plan, what feasible recovery actions exist, what each costs or saves relative to doing nothing, and lets the operations manager review, test changes, and approve. Product rules, vocabulary, and scope: `CLAUDE.md`, "Product (read first)".

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
| R · Recovery engine | `lane/R-engine` | `backend/app/recovery/`, `backend/app/baselines/`, `backend/app/planning/` (performance and edit handling), `backend/tests/lane_r/`, the `/api/recovery/*` handlers, economic entries in `config.parameters` | frontend, `backend/app/replay/`, `data/weather/`, docs |
| C · Recovery Canvas | `lane/C-canvas` | `frontend/` except `src/views/season/`, `src/api/generated.ts`, `src/mocks/recorded/` | backend, data, docs |
| W · Weather evidence and trust | `lane/W-evidence` | `backend/app/replay/`, `data/weather/`, `data/demo/cases/`, `frontend/src/views/season/`, `docs/`, `README.md`, exception handlers in `backend/app/api/main.py`, `scripts/freeze.sh`, `scripts/record_mocks.py`, `backend/tests/lane_w/`, the `/api/storms`, `/api/cases`, `/api/season-replay` handlers | `backend/app/recovery/`, `backend/app/planning/`, the rest of `frontend/` |

Lanes A, B, and C from the first build day are archived in `lanes/_archive/`. Read them for history only.

Shared and frozen: `backend/app/contracts/` and the generated files `contracts/openapi.json` and `frontend/src/api/generated.ts`. Change them only through `docs/CONTRACTS.md`. The tiny expected results in `data/demo/tiny/expected/` are ground truth. Do not edit them to make a test pass.
Each lane's full brief: `lanes/<lane>/BRIEF.md`. Its checklist: `lanes/<lane>/feature_list.json`.

## Continue from here

Every session, any agent, starts the same way. The full ritual is in `CLAUDE.md`, "Workflow (today's build)".

1. Open `lanes/<lane>/PROGRESS.md` and do what its "Continue from here" block says.
2. That block names the branch, the setup and check commands, what to read, and the next item.
3. Work on one feature-list item at a time. Before you stop, rewrite the block so the next session, human or agent, can continue cold.

## Done means

- The item's `acceptance` command passes, or its evidence file exists and you opened it.
- The lane check in `lanes/<lane>/BRIEF.md` passes.
- Then set `"passes": true`, update `PROGRESS.md`, and commit.

## Commits and merges

- Commit small, on your lane branch, with an imperative message: `lane-a: validator checks inventory by day`.
- `git add` new files yourself.
- When a P0 item lands and the lane check passes, push the lane branch and open a PR to `main` with `gh pr create`. A human merges it. Integrate early, not only in the morning.
- Never push to `main`. Never force-push. Never merge your own PR.

## Coordination (files only)

- `lanes/<lane>/PROGRESS.md`: handoff note. Done, In progress, Next, Blockers.
- `lanes/<lane>/NEEDS.md`: requests to another lane. Name the lane, the need, and what you use until then.
- `contracts/CHANGE_REQUESTS.md`: contract changes. See `docs/CONTRACTS.md`.

## Guides

Plain Markdown. Any agent can read them. Claude Code also loads them as skills.

- `.claude/skills/plain-english/SKILL.md`: UI copy, explanations, commits, docs.
- `.claude/skills/contracts/SKILL.md`: reading the models, regenerating types, change requests.
- `.claude/skills/ops-optimization/SKILL.md`: CP-SAT and HiGHS patterns (lanes A and B).
- `.claude/skills/data-provenance/SKILL.md`: manifests, labels, time zones (lane A).
- `.claude/skills/design-system/SKILL.md` and `docs/DESIGN.md`: UI rules (lane C).

## Operator controls

- `touch AGENT_STOP` at the repo root means stop. Any agent that sees it stops working. Claude Code enforces it with a hook.
- A note in `STEER.md` (all lanes) or `lanes/<lane>/STEER.md` (one lane) overrides your current plan. Read it, follow it, then empty the file.
