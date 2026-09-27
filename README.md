# Rollout Planner

A planning and recovery analysis tool for residential battery installers like Base. It takes an installation plan plus a disruption (a crew out, reduced capacity, a readiness change, or an appointment change), finds the best recovery, and explains which commitments are at risk and why.

It is not a customer booking tool. It does not pick appointments or send anything to customers.

Status: the backend works end to end. It covers data loading, input checks, battery valuation, the CP-SAT planner, the independent validator, baselines, diffs, counterfactuals, and the API. The UI is in progress. Spec: [`docs/SPEC.md`](docs/SPEC.md).

## Quick start

Needs `uv`, `make`, and bash (macOS, Linux, WSL, or Git Bash on Windows). The UI also needs `pnpm`.

"Verified" means the command ran and passed on 2026-09-26 on Windows with Git Bash. macOS and Linux are not verified.

| Command | What it does | Status |
|---|---|---|
| `make setup` | Install Python deps. Installs frontend deps once `frontend/package.json` exists | verified (backend part) |
| `make api` | API on http://localhost:8000. Builds every value table in the background. `GET /api/health` reports `values: ready` when done | verified |
| `make check-contracts` | Contract tests plus a check that `contracts/openapi.json` is current | verified |
| `make check-a` | Data, valuation, and validation lint/tests | verified |
| `make check-b` | Planning, baselines, compare, and API lint/tests | verified |
| `make mocks` | Re-record the UI mock responses from the in-process API | verified |
| `make types` | Write `contracts/openapi.json`, then generate `frontend/src/api/generated.ts` | OpenAPI half verified. The TypeScript half needs the frontend |
| `make check` | All of the above plus `check-c` | needs the frontend |
| `make dev`, `make dev-live`, `make e2e`, `make demo` | UI commands | need the frontend |

Try the API without the UI:

```bash
make api
curl -s localhost:8000/api/scenarios
curl -s -X POST localhost:8000/api/recovery/options -H 'content-type: application/json'   -d '{"scenario_id":"standard","revision":1,"disruption":[{"kind":"remove_crew_day","crew_id":"BA","date":"2018-06-07"}]}'
```

Every error is an `ApiError` with `code` and `message`. The first cold start builds the standard value table in the background, which took 46 s on the test laptop.

## Tech stack

- Backend: Python 3.13, FastAPI, Pydantic, OR-Tools CP-SAT, HiGHS (`scipy.optimize.milp`), `uv`
- Frontend: React, TypeScript, Vite, Vitest, Playwright, MSW
- Contracts and tooling: OpenAPI (`contracts/openapi.json`), generated TypeScript client (`frontend/src/api/generated.ts`), Make

## Architecture diagram

```mermaid
flowchart LR
    A[data/demo + data/manifests<br/>Synthetic and modeled inputs] --> B[Backend loaders and validators]
    B --> C[Recovery engine and valuation]
    C --> D[FastAPI /api/*]
    D --> E[Frontend Recovery Canvas]
    E --> F[Review recovery option and approve plan]
```

## How to reproduce the demo

1. Copy both sample env files.
2. Start backend and frontend.
3. Open the UI and run the disruption flow.

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
make setup
make dev-live
```

Open the app at `http://localhost:5173`.

- Backend env vars (`.env`):
  - `DEMO_DIR=data/demo`
  - `API_PORT=8000`
  - `SOLVE_TIME_LIMIT_S=15`
- Frontend env vars (`frontend/.env`) for the live demo path above:
  - Set `VITE_API_MODE=live` to proxy `/api` to `localhost:8000`
- Optional mock-only run:
  - Set `VITE_API_MODE=mock`
  - Run `make dev` instead of `make dev-live`
- API keys: none are required for this repo. Data is local files plus recorded mocks.
- Demo script: [`docs/DEMO.md`](docs/DEMO.md)

## Datasets and provenance

- `data/demo/tiny`: synthetic hand-built fixture with expected outputs in `data/demo/tiny/expected/`.
- `data/demo/standard`: synthetic scenario for larger-scale tests.
- `data/demo/standard_real`: mixed dataset for realism tests. Provenance is documented per file in `data/manifests/*.json`.
- `data/manifests/ercot_np6_785_2018.json`: ERCOT 2018 historical prices used as hindsight modeled value input.
- `data/manifests/resstock_amy2018_tx_100.json`: synthetic building sample derived from NREL ResStock.
- `data/manifests/hcad_parcels.json`: parcel-based candidate site source used for modeled locations.

## Layout

```text
backend/app/contracts   frozen Pydantic models (source of truth for types)
backend/app/data        loading, input checks, fixtures, data prep
backend/app/valuation   battery MILP, value table
backend/app/validate    independent plan validator
backend/app/planning    CP-SAT model, strict and recovery modes
backend/app/baselines   EDF and nearest-cluster baselines
backend/app/compare     plan diffs
backend/app/api         FastAPI app
frontend/               React app, MSW mocks, Playwright
data/demo/tiny          hand-built 6-job fixture with expected results
contracts/              generated openapi.json and the change log
lanes/                  archived and in-progress implementation lane notes
docs/                   spec, decisions, contracts, design, demo script
```

## Data honesty

All tiny and standard inputs are synthetic until a manifest in `data/manifests/` says otherwise. The UI labels synthetic data. Historical-price value is a hindsight benchmark, not a forecast.

## Known limitations

- UI status is in progress. Live API coverage depends on branch state. If a screen is not live-wired yet, use mock mode (`VITE_API_MODE=mock` and `make dev`).
- Travel is a fixed allowance per crew-day. The planner does not optimize routes or stop order.
- Weather replay is parked in `lanes/_parked/weather` and is not in the main demo flow.
- Live external feeds and autonomous approval are out of scope in this build.

## Next steps

- Complete live API wiring for every Recovery Canvas screen so mock mode is only needed for offline demos.
- Expand integration and e2e coverage for recovery options and approval.
- Add more documented observed datasets and keep synthetic versus modeled labels in UI and docs.
- Improve recovery comparisons with clearer risk and commitment impact summaries.

## Team workflow notes

Internal team and agent orchestration notes are in [`docs/TEAM_AGENT_WORKFLOW.md`](docs/TEAM_AGENT_WORKFLOW.md).
