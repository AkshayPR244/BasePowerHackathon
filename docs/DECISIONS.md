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

- **Agent-neutral lanes, no init scripts.** `AGENTS.md` holds the rules for any coding agent. `CLAUDE.md` imports it and adds Claude-only extras. Each lane's `PROGRESS.md` opens with a "Continue from here" block: branch, setup, check, reading list, next item. One line starts any agent: "Read AGENTS.md, then lanes/<lane>/PROGRESS.md, and continue from there."
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

## Backend hardening (2026-09-26)

- **Standard solves with 8 CP-SAT workers plus a hidden tie-break stage.** A fixed seed does not make parallel CP-SAT deterministic. In 5 runs, 8 workers returned 4 different plans with equal objectives. A final `canonical` stage picks one plan among equal optima, so replays and recordings reproduce. Measured on standard: strict 0.31 to 0.36 s and late-shipment recovery 1.7 to 2.0 s, down from about 1.1 s and 3.7 s with 1 worker. CP-SAT's deterministic interleaved mode was slower (2.8 s and 5.8 s). The tie-break stage is not reported and never changes a result's status.
- **Value tables build at API startup in a background thread.** A cold standard table took 46 s inside the first request.

## Objective order (changed from SPEC section 7 on 2026-09-26)

- **Order: deadline misses, total delay, changed installs, operating value, travel.** Strict mode: changed installs, operating value, travel. The spec ranked operating value above changed installs. A recovery tool should not move customers for small modeled value. Each changed install is a customer contacted. Value is now a tie-breaker.
- **Measured on standard.** Strict with no disruption changed 13 of 30 planned installs under the spec order and 0 now. Keeping the plan gives up $39.44 of modeled value ($1,998.39 to $1,958.95) and raises travel from 1,190 to 1,550 min. Late-shipment recovery: 3 jobs late and 13 delay days in both orders, with 10 changed installs instead of 15.
- **The tiny expected results list stages in the new order.** Their values, assignments, and objectives did not change, because tiny has equal values.

## First principles for the standard scenario (2026-09-26)

- **Every generated number follows a stated rule or a cited source,** listed in `scenario.yaml` under `parameters`. Deadlines are ready date + 5 business days (US federal holidays excluded). The current plan is an earliest-deadline-first booking. Deliveries are sized to the planned installs.
- **Travel comes from geometry:** (2 x depot-to-cluster + 2 x mean site radius) x 1.417 circuity / 40 km/h. Circuity is the US nationwide detour index (Boscoe, Henry, Zdeb 2012). Speed is an assumption.
- **Battery comes from the Powerwall 3 datasheet:** 13.5 kWh, 5 kW charge, 11.5 kW output. The datasheet gives no grid-charge round trip, so we use its 89% solar-to-battery-to-home/grid figure and split it as sqrt(0.89) per direction. This is a labeled approximation.
- **Weather uses observed METAR reports from Houston Hobby (IEM ASOS archive), not Open-Meteo.** Open-Meteo's reanalysis reported no thunderstorm codes for Houston in June and July 2018 (1 lost weekday). METAR reported thunder on 10 weekdays. The lightning rule needs observed thunder, so we use METAR. The rule: any `TS` report or at least 7.6 mm/h (AMS heavy rain) during 08:00 to 17:00 loses the crew-day.
- **The late-shipment example no longer makes any job late** under the rule-based deadlines. We report that as is.

## Two visits per home (2026-09-26)

- **Each home needs an install (the electrical disconnect visit), then a battery day (the battery is placed) at least 1 business day later.** Install crews and battery crews are separate. The two visits compete for different crews, so a lost crew-day on one side has a different impact than on the other. That is the recovery question a single-visit model cannot ask.
- **Deadline, energy value, and inventory attach to the battery day.** Value starts after the battery is in place. The install alone earns nothing.
- **Visits moved and customers to reschedule are both reported.** A customer with two moved visits is still one phone call. Objective order is unchanged: deadline misses, total delay, changed visits, energy value, travel.
- **Timing is assumed, not sourced:** install 90 to 180 min, battery day 60, 75, or 90 min (about 75, so 5 to 6 a day with travel). None of it comes from any company's internal data.
- **Standard: 45 homes, 2 install crews, 1 battery crew, 10 business days.** The battery crew is the bottleneck at 84.6% utilization in the strict plan, with install crews at 66.9%. Two settings make that load feasible on time, both tagged assumed: battery crews start on the second window day (no install is finished on the first), and deadlines are ready date + 6 business days (+5 made 45 homes infeasible).
- **The current plan is this tool's strict plan for the undisrupted scenario** (single worker, deterministic work limit, so it is reproducible). The earlier earliest-deadline-first booking could not place all 45 homes. This matches the workflow: plan first, then a disruption hits.
- **Two solver fixes came out of this.** A stage whose objective is a constant no longer counts as "optimal" before any solve proved feasibility; it used to turn an infeasible plan into `timeout_no_incumbent`. Each non-final lexicographic stage now uses at most half of the remaining budget, so a slow early stage cannot starve "changed visits". A new per-skill capacity cut made the first recovery stage prove in 2.4 s instead of 38 s on the battery-crew disruption.

## Skills

- **frontend-design** (anthropics/claude-plugins-official) and **webapp-testing** (anthropics/skills): vendored into `.claude/skills/` with their Apache-2.0 licenses. Vendoring means teammates need no plugin install and subagents can preload them by name.
- **skill-creator** (anthropics/skills): not vendored. We only needed it tonight to write the project skills. Install the plugin if you want to edit skills later.

## Stack defaults we kept

- **Hooks from anthropics/cwc-long-running-agents:** `kill-switch.sh` and `commit-on-stop.sh` are copied as is except for the repo-root path. `steer.sh` is adapted as above.
