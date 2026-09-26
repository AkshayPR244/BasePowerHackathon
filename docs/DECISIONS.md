# Decisions

One line of reasoning each. Newest changes at the bottom of each section.

## Stack

- **Scheduling solver: OR-Tools CP-SAT, not SciPy milp.** CP-SAT gives solution hints for minimal-disruption replans, clean lexicographic re-solves, and infeasibility explanations through assumption literals.
- **Battery valuation solver: SciPy milp (HiGHS).** It needs continuous variables plus a binary charge/discharge mode, which CP-SAT handles poorly.
- **Backend: Python 3.12, uv, FastAPI, Pydantic v2, pandas, pyarrow, pytest, ruff.** Ruff replaces a separate formatter and linter to keep `make check` fast.
- **Frontend: pnpm, React + TypeScript + Vite, Tailwind v4 on CSS variable tokens, TanStack Query, Zustand, MSW, Vitest, Playwright, @fontsource.** Self-hosted fonts keep the app usable offline.
- **Types: Pydantic models are the single source of truth.** FastAPI exports `contracts/openapi.json`, openapi-typescript generates `frontend/src/api/generated.ts`, and openapi-fetch gives a typed client. Nobody hand-writes shared types.
- **Units:** IDs are strings, durations integer minutes, energy kWh, power kW, prices USD/MWh, value USD. Scheduling dates use America/Chicago. Energy timestamps use UTC.
- **Platforms: macOS and Linux/WSL.** Native Windows works for the backend and frontend but hooks and the Makefile assume bash.

## Changes from the scaffold prompt

- **Framing: planning and recovery analysis, not booking.** The spec's `appointments.csv` is the current installation plan. The contract calls it `Scenario.current_plan` of `PlannedInstall` rows, the file is `current_plan.csv`, and the metric is `changed_installs`. Edits are disruptions or interventions. `docs/SPEC.md` stays verbatim.
- **The scaffold ships no running product code.** It holds frozen contracts, the tiny fixture with expected results, lane briefs, and the harness. The loader, API, OpenAPI export, generated TS types, MSW mocks, and app shell are each lane's first items. Nothing was installed or built to make this scaffold.
- **No MapLibre. The map is plain SVG.** We render about 30 points and 3 cluster outlines with no basemap. A WebGL map library adds weight and setup for no visible gain. `Site` carries `lon`/`lat` and `Cluster` carries `outline`, so the UI needs no GeoJSON parsing.
- **Integrate continuously, not only at a morning merge.** Lane B needs Lane A's validator, and Lane C needs the live API. Each lane opens a small PR to `main` when a P0 item lands. Path ownership keeps these PRs conflict-free. The integrator subagent still exists for the final pass.
- **Stateless API.** Compare takes both plans in the body. Counterfactual takes the base request, the base plan, and the intervention. No server storage means no cache invalidation bugs and no lost state on reload.
- **Baselines use `POST /api/plans` with `algorithm`.** One endpoint and one result model means one validator path and one UI path.
- **Strict mode reports hard-blocked jobs instead of failing.** A job with no legal (crew, day) option is listed as `blocked` with reason codes. No schedule can fix it, so it must not hide the feasibility of the other jobs. A job that has options but none by its deadline still makes strict mode infeasible.
- **Validator interface is fixed today.** `app.validate.validate_plan(scenario, result)` returns `checked: false` until Lane A fills it. The UI shows "Not validated" for that state. We never show a green check we did not earn.
- **`make dev` will run the frontend on recorded mocks.** It needs no backend. `make dev-live` runs both. This keeps Lane C unblocked.
- **`make check` excludes Playwright.** Browser tests are slow and need a browser install. `make e2e` runs them.
- **Tiny fixture uses 2018 dates (4 to 6 June).** They line up with the ERCOT 2018 replay window in the spec.
- **Scenario inputs stay in the spec's file formats.** CSV for tables, YAML for config, GeoJSON for geometry. The loader turns them into contract models, so no lane parses files twice.
- **Tiny expected responses come from a throwaway exhaustive enumerator.** It found a unique optimum in every case. The files say so in their `assumptions`. Lane A writes the independent enumerator that must agree.
- **`httpx2` replaces `httpx` for the test client.** Starlette deprecated `httpx` for `TestClient`.
- **No verify-gate hook.** The cwc repo's `verify-gate` and `track-read` hooks guard a single results file. Our `feature_list.json` acceptance commands and the evaluator subagent cover that job.
- **Steer hook supports per-lane files.** `lanes/<lane>/STEER.md` targets one lane by subagent type or branch. `STEER.md` at the root targets every agent.

## Skills

- **frontend-design** (anthropics/claude-plugins-official) and **webapp-testing** (anthropics/skills): vendored into `.claude/skills/` with their Apache-2.0 licenses. Vendoring means teammates need no plugin install and subagents can preload them by name.
- **skill-creator** (anthropics/skills): not vendored. We only needed it tonight to write the project skills. Install the plugin if you want to edit skills later.

## Stack defaults we kept

- **Hooks from anthropics/cwc-long-running-agents:** `kill-switch.sh` and `commit-on-stop.sh` are copied as is except for the repo-root path. `steer.sh` is adapted as above.
