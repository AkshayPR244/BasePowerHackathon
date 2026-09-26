# Rollout Planner

A planning and recovery analysis tool for residential battery installers like Base. It takes an installation plan plus a disruption (crew out, late shipment, slipped approval), finds the best recovery, and explains which commitments are at risk and why.

It is not a customer booking tool. It does not pick appointments or send anything to customers.

Status: scaffold only. Frozen contracts, the tiny fixture with expected results, lane briefs, and the agent harness exist. No product code exists yet. Every command below is planned until a lane verifies it. Spec: [`docs/SPEC.md`](docs/SPEC.md).

## Quick start

Needs `uv`, `pnpm`, `make`, and bash (macOS, Linux, or WSL).

| Command | What it does | Status |
|---|---|---|
| `make setup` | Install Python and frontend deps, and the Playwright browser | planned |
| `make dev` | Frontend on http://localhost:5173 with recorded mocks. No backend. | planned |
| `make dev-live` | Backend on :8000 plus frontend proxied to it | planned |
| `make check` | Contracts, lane A, lane B, lane C checks | planned |
| `make e2e` | Playwright against mocks. Screenshots go to `frontend/e2e/screenshots/` | planned |
| `make types` | Regenerate `contracts/openapi.json` and `frontend/src/api/generated.ts` | planned |
| `make mocks` | Re-record MSW responses from the in-process API | planned |
| `make demo` | Reset demo data and run the live app | planned |

## Start a lane

Each teammate runs one lane. Each lane runs in its own clone or worktree.

```bash
git fetch origin
git switch lane/a-data        # or lane/b-planning, lane/c-ui
./lanes/A-data/init.sh        # or B-planning, C-ui
claude "Follow CLAUDE.md. You are lane A. Do the session start ritual, then work through lanes/A-data/feature_list.json."
```

For overnight runs, start Claude Code with `--permission-mode acceptEdits`. The allowlist in `.claude/settings.json` covers the usual commands. Anything else waits for approval.

- Stop an agent: `touch AGENT_STOP`. Resume: `rm AGENT_STOP`.
- Redirect an agent: write a note to `lanes/<lane>/STEER.md` or `STEER.md`.

One session can also run all three lanes as subagents. See "Orchestrator mode" in [`CLAUDE.md`](CLAUDE.md).

## Layout

```text
backend/app/contracts   frozen Pydantic models (source of truth for types)
backend/app/data        lane A: loading, input checks, fixtures, data prep
backend/app/valuation   lane A: battery MILP, value table
backend/app/validate    lane A: independent plan validator
backend/app/planning    lane B: CP-SAT model, strict and recovery modes
backend/app/baselines   lane B: EDF and nearest-cluster baselines
backend/app/compare     lane B: plan diffs
backend/app/api         lane B: FastAPI app (empty today)
frontend/               lane C: React app, MSW mocks, Playwright
data/demo/tiny          hand-built 6-job fixture with expected results
contracts/              generated openapi.json and the change log
lanes/                  briefs, feature lists, progress notes per lane
docs/                   spec, decisions, contracts, design, demo script
```

## Data honesty

All tiny and standard inputs are synthetic until a manifest in `data/manifests/` says otherwise. The UI labels synthetic data. Historical-price value is a hindsight benchmark, not a forecast.
