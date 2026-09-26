# Lane R · Recovery engine

## Mission
Rollout Planner is a deterministic disruption-recovery planner for installation operations. It shows what broke, how the disruption cascades through the current plan, what feasible recovery actions exist, what each costs or saves relative to doing nothing, and lets the operations manager review, test changes, and approve. R is the product, C is the experience, H makes it demo-safe. Weather replay is a parked nice-to-have (`lanes/_parked/weather`).

Lane R builds the product: given the current plan and a known disruption, return the impact, the no-action outcome, and a short list of feasible recovery actions. Each action is solved, validated, priced, and labeled as a business action ("Crew IB +2h overtime"). The operator can test any manual change and approve an option.

## Current state
- Done on `main`: the two-visit `standard` scenario (45 homes, install crews IA and IB, battery crew BA, battery side at 84.6% and the bottleneck). The CP-SAT planner with strict and recovery modes and the independent validator on every plan. EDF and nearest-cluster baselines. Compare and counterfactual endpoints. Energy value table from ERCOT 2018.
- Frozen in this scaffold: every recovery contract (see `docs/CONTRACTS.md`), the stub service `backend/app/recovery/service.py` (reads `backend/app/recovery/fixtures/*.json`), and stub endpoints `POST /api/recovery/options`, `/evaluate`, `/approve`. Stubs send `stub=true` and the header `X-Rollout-Stub: true`.
- Not built: everything behind the stubs. The new edits return `invalid_input` "not implemented yet" from `POST /api/plans`.

## Owns
- `backend/app/recovery/`
- `backend/app/baselines/`
- `backend/app/planning/` (performance and edit handling only; no change to the objective order)
- `backend/tests/lane_r/`
- The `/api/recovery/*` handlers in `backend/app/api/main.py`
- Economic entries in `config.parameters` (via the scenario generator's parameter list) and the economic defaults in `backend/app/recovery/`
- `lanes/R-engine/`

## Must not touch
- `backend/app/contracts/` except additive, logged changes (see `docs/CONTRACTS.md`)
- `backend/app/validate/` (independent validator: call it, never change it to make a plan pass)
- `backend/app/replay/`, `data/weather/`, `data/demo/cases/` (parked weather stubs)
- `frontend/` (Lanes C and H)
- `docs/`, `README.md` (Lane H), except `docs/CONTRACTS.md` entries for additive contract changes

## Consumes
- `app.planning.solve.plan`, `app.validate.validate_plan`, `app.valuation.value_table`, `app.compare.diff.diff_plans`.
- The frozen contracts: `RecoveryOption`, `RecoveryOptionsResult`, `ImpactAnalysis`, `RecoveryCounts`, `RecoveryEconomics`, `EconomicLine`, `EconomicAssumption`, `Explanation`, `CrewLoad`, `ApproveResult`, and the edits `ReduceCrewDay`, `ChangeAppointment`, `ExtendCrewDay`, `PinVisit`, `MoveVisit`.

## Provides
- `backend/app/recovery/service.py`: `recover(scenario, disruption, current_plan=None, economics=None, interactive=False) -> RecoveryOptionsResult`, `evaluate(scenario, disruption, interventions, current_plan=None, economics=None, interactive=True) -> RecoveryOption`, `approve(scenario, option) -> ApproveResult`. Keep the signatures. A parked weather replay may call `recover()` later.
- `POST /api/recovery/options`, `/evaluate`, `/approve` with `stub=false`.

## Files to create
| Path | Purpose |
|---|---|
| `app/recovery/repair.py` | No action: affected visits wait for their own crew's next open slot, nothing else moves |
| `app/recovery/edits.py` or `app/planning/edits.py` | Apply `reduce_crew_day`, `change_appointment`, `extend_crew_day`, `pin_visit`, `move_visit` to scenario inputs before solving |
| `app/recovery/impact.py` | Affected visits, lost capacity minutes, cascade, deadlines at risk |
| `app/recovery/options.py` | No action, rebalance, overtime search, temporary capacity |
| `app/recovery/economics.py` | Net impact, advantage vs no action, lines, cost per deadline recovered |
| `app/recovery/explain.py` | One plain sentence per changed visit, naming the constraint |
| `app/recovery/service.py` | Replace the stub bodies. Keep the signatures |
| `tests/lane_r/test_*.py` | One file per feature item |

## Scope

### P0 (in order)
1. **No action** as a first-class `RecoveryOption` (kind `no_action`). Repair rule: every visit that lost its slot waits for its own crew's next open slot. Nothing else moves. Precedence holds. The result passes the validator.
2. **Disruption edits**: `reduce_crew_day` (reduced capacity) and `change_appointment` (the customer is only available in a window). `remove_crew_day` and `change_ready_date` already exist.
3. **Intervention edits**: `extend_crew_day` (overtime), `pin_visit` (keep this visit where it is), `move_visit` (drag). `add_crew_day` already exists. Applied to scenario inputs before solving. No solver changes.
4. **`recover()`**: options no action, rebalance existing crews, overtime (search `extend_crew_day` over the affected crew-days), temporary capacity (`add_crew_day`). Each option is solved, validated, and labeled as an action.
5. **Impact analysis**: directly affected visits, lost capacity minutes, cascade install → battery day → deadline, deadlines at risk. `ImpactAnalysis.headline` is one plain sentence.
6. **Economics**: headline `net_impact_usd` and `advantage_vs_no_action_usd`. Breakdown lines with a basis. Deadlines recovered. Cost per deadline recovered (null when none). Crew regular and overtime cost (BLS OEWS Houston electrician wage, cited with year, × 1.5 overtime). Max overtime per crew-day. Temporary crew-day cost. Every number is an `EconomicAssumption` with a source or the tag assumed and a one-line reason. Penalty dollars exist but are off by default.
7. **`POST /api/recovery/evaluate`** for any manual change. Returns a `RecoveryOption` of kind `custom`.

### P1
8. Interactive mode: about 2 s budget, warm start from the current plan, "Best found" when not proven, cache by scenario hash plus edits. Today the battery-crew-out case takes 9.7 s.
9. Pin semantics: report what protecting a visit costs (advantage lost vs the unpinned option).
10. `POST /api/recovery/approve` returns the chosen option as the new current plan.
11. One plain-sentence explanation per changed visit, naming the constraint.
12. `lowest_modeled_cost` flag on exactly one option. Never "Recommended".

### P2
13. Per-crew load before and after (`crew_load`).
14. Customer reschedule as an intervention.

## Definition of done
- `recover()` on `standard` with battery crew BA out Thu 7 Jun returns no action plus three action options, every one validated, with impact, counts, economics, and explanations.
- `evaluate()` handles each new edit. `approve()` returns a plan that loads as `current_plan`.
- `stub=false` on every recovery response. No `X-Rollout-Stub` header.
- Lane check passes (below). `make check-contracts`, `make check-a`, `make check-b` pass.

## Lane check
`cd backend && uv run ruff check app/recovery app/baselines app/planning tests/lane_r && uv run pytest -q tests/lane_r tests/lane_b tests/contract`

## Cut list (cut in this order)
1. Reduced capacity (`reduce_crew_day`).
2. Appointment change (`change_appointment`).
3. Approve chaining (approving an option on top of an approved option).
Never cut no action, validation, or the economics basis lines.

## Working rules
- Branch `lane/R-engine`. Pull `origin/main` at session start.
- One PR per feature item. Merge only after the checks and an evaluator PASS. Never push to `main`. Never merge your own PR overnight.
- Merge your P0 items early. At the hour-4 sync, C swaps one flow to your live endpoints and H runs the live e2e.
- Update `lanes/R-engine/PROGRESS.md` after every item. Write requests to other lanes in `lanes/<their lane>/NEEDS.md`.
