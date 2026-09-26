# Status at the start of the recovery build (2026-09-27)

Inventory of `main` before lanes R-engine, C-canvas, and W-evidence start. Measured this session unless marked UNVERIFIED.

## Last night's lanes

The R-recovery, W-weather, and H-hardening scaffold was reverted before any commit. No branch, worktree, or folder from it exists on `main` or any remote. Nothing to recover. The day 1 lanes (A-data, B-planning, C-ui) worked well and are archived in `lanes/_archive/` as templates.

## Exists and works

- **Standard two-visit scenario.**
  - Setup: 45 homes, 90 visits, install crews IA and IB (20 crew-days), battery crew BA (9 crew-days, from day 2), 10 business days.
  - Utilization: battery 84.6% (the bottleneck), install 66.9%.
  - Every number is a stated rule or a cited source in `config.parameters`.
- **CP-SAT planner with strict and recovery modes.**
  - Five lexicographic stages: deadline misses, total delay, changed visits, energy value, travel. Energy value is a tie-breaker.
  - One time budget. Each non-final stage gets at most half of what remains.
  - Reproducible with 8 workers.
- **Independent validator on every plan.** It checks precedence (a battery day comes at least 1 business day after its install), visit skill, capacity, inventory, locks, and objectives. A plan that fails raises HTTP 500 `invalid_plan`.
- **Exhaustive enumerator** matches the planner on `tiny` (5 cases) and `tiny_two_visit` (4 cases).
- **Baselines:** earliest-deadline-first and nearest-cluster-first. Both respect precedence and pass the validator. Both rebuild the plan from scratch, so their "visits moved" counts are high by construction.
- **Energy value table** from ERCOT 2018 LZ_HOUSTON prices and the Powerwall 3 datasheet. Cached and warmed at API startup.
- **Endpoints that work:**
  - `GET /api/health`, `GET /api/scenarios`, `GET /api/scenarios/{id}`
  - `POST /api/plans` (edits: remove_crew_day, add_crew_day, delay_inventory, change_ready_date, force_include)
  - `POST /api/plans/compare`, `POST /api/plans/counterfactual`
- **UI workspace (PR #5).**
  - Tiny flow: calendar, map, inspector, compare, counterfactuals, export, dark mode.
  - Recorded mode and live mode both work. 4 of 5 e2e pass live.
- **Measured on standard, recovery mode:**

  | Disruption | Optimizer | Earliest deadline first |
  |---|---|---|
  | Install crew IA out Thu 7 Jun | 0 deadlines missed, 9 visits moved, 0.8 s | 1 late, 7 unscheduled, 74 visits moved |
  | Battery crew BA out Thu 7 Jun | 4 unscheduled, 4 visits moved, about 9.7 s, "feasible" not proven | 4 late, 8 unscheduled, 65 visits moved |

## Stubbed (seams frozen in this scaffold)

- Endpoints return fixtures with `stub: true` and the header `X-Rollout-Stub: true`:
  - `POST /api/recovery/options`, `/evaluate`, `/approve`
  - `GET /api/storms`, `/api/cases`, `/api/season-replay`
- **Fixtures** (`scripts/build_stubs.py`) use real planner results on `standard` for the 14 Jun 2018 storm case (all three crews out):

  | Option | Deadlines missed | Visits moved |
  |---|---|---|
  | No action (earliest-deadline-first stand-in) | 13 | 72 |
  | Rebalance existing crews | 4 | 25 |
  | Temporary battery crew on 15 Jun | 1 | 49 |

  Economics, explanations, and the overtime option are placeholders.
- **Storm events** are real routine METAR observations at Houston Hobby for June and July 2018. They are not yet committed as a dataset with a manifest.
- **Python seams:** `app.recovery.service.recover / evaluate / approve` and `app.replay.service.storms / cases / season_replay`.
- **Five new edits** return `invalid_input` "not implemented yet": reduce_crew_day, change_appointment, extend_crew_day, pin_visit, move_visit.

## Missing

- **Recovery engine (lane R):**
  - repair-rule no action
  - the new edits
  - real options and overtime search
  - impact analysis
  - economics with cited wages
  - evaluate, approve
  - interactive mode (the battery-crew-out case takes about 9.7 s today)
- **Recovery Canvas UI (lane C).** The current UI is the day 1 workspace. It has never rendered two-visit data (UNVERIFIED).
- **Weather evidence (lane W):**
  - weather dataset and manifest
  - cases for every storm
  - the season replay through `recover()`
  - stress tests
  - `docs/REPLAY_RESULTS.md`, `docs/FIRST_PRINCIPLES.md`, README limitations
- **Known defects:**
  - The 500 handler returns exception text to the client (`backend/app/api/main.py`, `_unexpected`).
  - The late-shipment example is still in README, `docs/DEMO.md`, `docs/CONTRACTS.md`, `scripts/record_mocks.py`, and the recorded mocks.
  - `frontend/src/lib/export.test.ts` and `e2e/shell.spec.ts` still expect "Not validated".
- **Data to verify:** 4 Jul 2018 METAR rainfall sums to 145 mm in work hours. Lane W checks it before use. It is a holiday, so no crew works that day anyway.

## Checks at scaffold time

`make check-contracts`, `make check-a`, and `make check-b` pass. Frontend typecheck and build pass. Frontend unit tests: 1 known failure, the stale "Not validated" test, assigned to C-01.
