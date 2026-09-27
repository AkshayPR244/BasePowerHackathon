# Contracts

Rollout Planner is a planning and recovery analysis tool for residential battery installers. It takes an installation plan plus a disruption (a crew out, reduced capacity, a readiness change, or an appointment change), finds the best recovery, and explains what is at risk and why.

The Pydantic models in `backend/app/contracts/` are the only definition of shared types. OpenAPI and TypeScript types are generated from them. Nobody hand-writes shared types.

Status: the models are frozen as of the scaffold commit. The API app, the OpenAPI export, the type generation, and the recorded mocks are planned lane items (Lane B-01, B-02, C-02). Commands below marked "planned" do not exist until those items land.

## Files

| File | Holds |
|---|---|
| `backend/app/contracts/models.py` | Inputs, edits, requests, responses, data products |
| `backend/app/contracts/enums.py` | All enums |
| `backend/app/contracts/units.py` | Annotated unit types, `SCHEDULING_TZ = "America/Chicago"` |
| `backend/app/contracts/hashing.py` | `scenario_hash(scenario, edits=())` |
| `contracts/openapi.json` | Generated from the FastAPI app (planned, Lane B) |
| `frontend/src/api/generated.ts` | Generated from `openapi.json` (planned, Lane C) |
| `contracts/CHANGE_REQUESTS.md` | Log of every contract change and proposal |

Every model inherits `Contract`: extra fields are rejected and NaN or infinity fail validation.

## Units

| Quantity | Type | Unit |
|---|---|---|
| IDs | `str` | none |
| Duration | `int` | minutes |
| Energy | `float` | kWh |
| Power | `float` | kW |
| Price | `float` | USD/MWh |
| Value | `float` | USD |
| Scheduling date | `date` | America/Chicago calendar day |
| Energy timestamp | `datetime` | UTC, timezone-aware |

Calculate at full precision. Round only for display.

## Models by role

- Inputs: `Site`, `Cluster`, `CrewDay`, `InventoryReceipt`, `PlannedInstall`, `BatteryConfig`, `ProvenanceNote`, `ScenarioConfig`, `Scenario`, `ScenarioSummary`.
- Edits (discriminated by `kind`, union type `Edit`). Disruptions: `RemoveCrewDay`, `DelayInventory`, `ChangeReadyDate`. Interventions: `AddCrewDay`, `ForceInclude`.
- The current plan: `Scenario.current_plan` is a list of `PlannedInstall` (site_id, crew_id, date, locked).
- Plan: `PlanRequest`, `PlanResult`, `Assignment`, `UnscheduledJob`, `CrewDayUsage`, `StageMeta`, `ObjectiveComponents`, `ValidationReport`, `ValidationIssue`, `Assumption`, `InputIssue`.
- Compare and counterfactual: `CompareRequest`, `PlanDiff`, `PlanChange`, `Slot`, `DiffSummary`, `CounterfactualRequest`, `CounterfactualResult`.
- Errors: `ApiError`.
- Data products: `ValueTableRow`, `Manifest`.

Key enums: `PlanStatus {optimal, feasible, infeasible, timeout_no_incumbent, invalid_input}`, `StageStatus` (same minus `invalid_input`, plus `skipped`), `Mode {strict, recovery}`, `Algorithm {cpsat, baseline_edf, baseline_nearest_cluster}`, `ReasonCode`, `JobState {scheduled, locked, late, unscheduled, blocked}`, `DataKind {observed, modeled, derived, assumed, synthetic}`.

## Endpoints

The API is stateless. The server stores no plans. The client sends back what it needs.

| Method and path | Request | Response | Notes |
|---|---|---|---|
| `GET /api/scenarios` | none | `list[ScenarioSummary]` | Bundled scenarios |
| `GET /api/scenarios/{scenario_id}` | none | `Scenario` | 404 if unknown. 422 `ApiError` with `input_issues` if the files fail validation |
| `POST /api/plans` | `PlanRequest` | `PlanResult` | Baselines use `algorithm`. `status=invalid_input` carries `input_issues` |
| `POST /api/plans/compare` | `CompareRequest {before, after}` | `PlanDiff` | Both are full `PlanResult`s |
| `POST /api/plans/counterfactual` | `CounterfactualRequest {request, base, intervention}` | `CounterfactualResult` | Solves `request` plus `intervention`, diffs against `base` |

A stub may answer 501 with an `ApiError` body for requests it cannot serve yet.

## Semantics

### revision and scenario_hash
- `PlanRequest.revision` is a client counter. The client bumps it on every edit. The server echoes it in `PlanResult.revision`. The client drops any response whose revision is not current.
- `scenario_hash` is sha256 over the scenario inputs (excluding `scenario_hash` and `revision`) plus the edit list, as canonical JSON. Always compute it with `app.contracts.hashing.scenario_hash(base_scenario, edits)`. `Scenario.scenario_hash` is the hash with no edits. `PlanResult.scenario_hash` is the hash with that plan's edits.

### Strict and blocked
- Strict requires every job with at least one legal (crew, day) option to finish by its deadline.
- A job with no legal option at all is `blocked`. It appears in `unscheduled` with reason codes and does not make strict infeasible.
- A job with options but none by its deadline makes strict `infeasible`.

### validation.checked
- `checked=false` means the independent validator did not run (stub). `valid` is then meaningless. The UI shows "Not validated".
- `checked=true, valid=true`: every constraint was recomputed from assignments and holds.
- `checked=true, valid=false`: `issues` lists each violation. Never show such a plan as a success.

### objective
- `None` when there is no plan (`infeasible`, `timeout_no_incumbent`, `invalid_input`).
- `jobs_unscheduled` includes blocked jobs. `jobs_blocked` counts them separately.
- `changed_installs` counts unlocked installs in `current_plan` that the recovery moved. The UI calls it "moved installs".
- `value_distinguishes_choices=false` means all site values were equal, so energy value changed no choice. Say so in the UI.

### stages
One `StageMeta` per lexicographic stage in order. Stages after a failed stage are `skipped`. `gap` is relative: `|value - bound| / max(1, |value|)`.

### Two visits per home (contract 1.1, additive)

A home can need two crew visits:

- **install**: the electrical disconnect visit. Install crews do it (`required_skill: install`).
- **battery day** (`battery_day`): the visit where the battery is placed. Battery crews do it (`required_skill: battery`).

The battery day comes at least `config.min_gap_business_days` business days after the install (default 1). The deadline, the energy value, and the battery from inventory belong to the battery day only. The install earns no value and is never late.

- `Site.visits`: empty for a one-visit home (then `duration_min` and `required_skill` describe the only visit). For a two-visit home it lists both visits with `job_id`, `visit_type`, `duration_min`, `required_skill`. `site_id` stays the home.
- **`assignments` can hold two entries per `site_id`.** Key them by `job_id` when it is set, else by `site_id`. `visit_type` says which visit it is. The same holds for `PlanChange` in diffs and for `UnscheduledJob`, where `job_id: null` covers the whole home (for example a blocked home).
- `current_plan` rows carry `job_id` for two-visit homes.
- Home-level counts: `jobs_on_time`, `jobs_late`, `jobs_unscheduled`, and `jobs_blocked` count homes, judged by the battery day.
- Customer metrics: `objective.visits_moved` counts planned visits moved or dropped (the same number as `changed_installs`, whose name predates two visits). `objective.customers_to_reschedule` counts distinct homes with at least one moved or dropped visit. `PlanDiff.summary.customers_to_reschedule` counts the same over a diff. Show "customers to reschedule" to operators: each is a customer contacted.
- The stage name `changed_installs` is unchanged and counts moved visits of both types.
- Validation adds `PRECEDENCE`: a battery day without an install at least the minimum gap earlier.

Scenarios with two-visit homes: `standard`, `tiny_two_visit`. `tiny` stays one-visit.

### Recovery and weather seams (contract 1.2, additive, stubbed)

The recovery flow: current plan, then a known disruption, then impact analysis, then recovery options, each solved and validated, then comparison, review, and approval.

**Edits.** All share the discriminated `Edit` union, so `/api/plans` and the recovery endpoints accept the same list.

| Role | kind | Fields | State |
|---|---|---|---|
| Disruption: crew unavailable | `remove_crew_day` | crew_id, date | works |
| Disruption: reduced capacity | `reduce_crew_day` | crew_id, date, available_min | not implemented (lane R) |
| Disruption: readiness change | `change_ready_date` | site_id, ready_date | works |
| Disruption: appointment change | `change_appointment` | job_id, available_from, available_to? | not implemented (lane R) |
| Intervention: overtime | `extend_crew_day` | crew_id, date, extra_min | not implemented (lane R) |
| Intervention: temporary capacity | `add_crew_day` | crew_id, date, available_min, skills, allowed_clusters | works |
| Intervention: pin a visit | `pin_visit` | job_id | not implemented (lane R) |
| Intervention: move a visit | `move_visit` | job_id, crew_id, date | not implemented (lane R) |

Until lane R lands them, the unimplemented edits return `status: invalid_input` with "Edit <kind> is not implemented yet."

**Recovery models**
- `RecoveryOption`: `option_id`, `kind` (no_action, rebalance, overtime, temporary_capacity, custom), `action_label` (a business action such as "Crew IB +2h overtime", never "Plan 3"), `intervention_edits`, `status`, `proven_optimal`, `result` (a full validated `PlanResult`), `diff_vs_original`, `diff_vs_no_action` (null on the no-action option), `counts`, `economics`, `overtime_min`, `explanations`, `crew_load`, `lowest_modeled_cost` (label it "Lowest modeled cost", never "Recommended"), `stub`.
- `RecoveryCounts`: deadlines_missed, deadlines_recovered (vs no action), delay_days, visits_moved, customers_to_reschedule, unscheduled.
- `RecoveryEconomics`: `net_impact_usd` (cost vs the original plan), `advantage_vs_no_action_usd` (no-action net impact minus this option's), `cost_per_deadline_recovered_usd` (null when none recovered), `lines[]` of `EconomicLine {label, amount_usd, kind: labor | value | penalty | other, basis}`. Positive amounts are costs. Every line states its basis. Penalty lines are off by default.
- `ImpactAnalysis`: headline, affected_job_ids, lost_capacity_min, `cascade[]` of `CascadeStep {kind: disruption | direct | pushed | commitment, label, job_ids}`, deadlines_at_risk.
- `EconomicAssumption`: key, value, unit, kind, source, editable. Overrides go in `economics_overrides` by key.
- `Explanation {job_id, text, constraint}` and `CrewLoad {crew_id, date, before, after}`.

**Recovery endpoints**
- `POST /api/recovery/options`: `RecoveryOptionsRequest {scenario_id, revision, current_plan?, disruption, economics_overrides?, interactive}` returns `RecoveryOptionsResult {revision, scenario_hash, impact, no_action, options, economic_assumptions, assumptions, stub}`. `revision` is echoed.
- `POST /api/recovery/evaluate`: `EvaluateRequest {scenario_id, revision, current_plan?, disruption, interventions, interactive}` returns one `RecoveryOption` of kind `custom`. Use it for knock-out, overtime stretch, drag, and pin.
- `POST /api/recovery/approve`: `ApproveRequest {scenario_id, revision, option}` returns `ApproveResult {new_current_plan, summary, stub}`.

**Weather evidence** (parked nice-to-have: these endpoints stay frozen stubs until weather returns)
- `GET /api/storms` returns `StormEvent[] {event_id, date, rainfall_mm, max_wind_kmh, thunder_hours, source, stub}`. Observed at Houston Hobby.
- `GET /api/cases` returns `Case[] {case_id, name, date, summary, storm_event_id?, disruption, modeled_rule, provenance, stub}`. The disruption is modeled. Say "This replay applies a modeled operational disruption to a real historical storm."
- `GET /api/season-replay` returns `SeasonReplay {replay_id, events[], totals, stress_tests?, stub}`. Each `SeasonReplayEvent` compares no action with the recovery engine for one case.

**Python seams**
- `app.recovery.service.recover(scenario, disruption, current_plan=None, economics=None, interactive=False) -> RecoveryOptionsResult`, plus `evaluate(...)` and `approve(...)`. A parked weather replay may call `recover()` later.
- `app.replay.service.storms()`, `cases()`, `season_replay()`.

**Stubs.** Until lanes R and W replace them, these return fixtures from `backend/app/recovery/fixtures/` and `backend/app/replay/fixtures/`, built by `scripts/build_stubs.py`. The fixtures use real planner results on `standard` for the 14 Jun 2018 storm case, with earliest-deadline-first standing in for no action. Economics and explanations are placeholders. Storm events are real observations. Every stub payload has `stub: true`, and the endpoint sets the header `X-Rollout-Stub: true`. The UI shows a stub label while `stub` is true.

## Regenerating (planned)

```bash
make types   # contracts/openapi.json, then frontend/src/api/generated.ts
make mocks   # frontend/src/mocks/recorded/*.json and index.json
```

Until the Makefile targets exist:

```bash
cd backend && PYTHONPATH=. uv run python ../scripts/export_openapi.py
./scripts/gen_types.sh
cd backend && PYTHONPATH=. uv run python ../scripts/record_mocks.py
```

Commit generated files in the same commit as the model change that caused them.

## Change protocol

After the scaffold commit, the contract is frozen.

### Additive changes: any lane, no human needed
1. Add an optional field with a default, a new model, or a new enum member that no existing field requires.
2. Regenerate types and mocks in the same commit.
3. Add one line to `contracts/CHANGE_REQUESTS.md` under "Log": date, lane, `Model.field`, reason.

### Breaking changes: wait for a human
Rename, remove, type or unit change, new required field, or changed meaning of a field.
1. Add a `PROPOSED` entry to `contracts/CHANGE_REQUESTS.md` with the change, the reason, and who is affected.
2. Keep working around it. Do not block.
3. A human approves, makes the change on main, and notifies the lanes through their `NEEDS.md`.

## Expected tiny responses

`data/demo/tiny/expected/*.json` were computed by a throwaway exhaustive enumerator. Each case has a unique optimum. They are the reference for Lane A's enumerator and Lane B's planner. Their `validation.checked` is false because no validator existed when they were built. Change them only with a human.

| File | Case |
|---|---|
| `plan_strict.json` | Strict, no disruption. 5 jobs on time. S-03 blocked |
| `plan_strict_remove_a_mon.json` | Strict, disruption: Crew A out Mon 4 Jun. Infeasible: N-02 has no legal date |
| `plan_recovery_remove_a_mon.json` | Recovery, disruption: Crew A out Mon 4 Jun. N-02 1 day late, N-03 moves to Wed |
| `compare_strict_vs_recovery.json` | Diff of the two plans above |
| `counterfactual_force_n02.json` | Intervention: force N-02 by deadline on the recovery plan. Infeasible |
| `counterfactual_add_c_mon.json` | Intervention: add Crew C (North) on Mon 4 Jun. All schedulable jobs on time |

### Lane R implementation notes (2026-09-27)

`EvaluateRequest.economics_overrides` is optional and uses the same keys as `/options`.
Recovery request revisions are carried through the service and approval checks.
Approval accepts only an unchanged live option issued by this server at the supplied revision,
revalidates its assignments, and returns bookings; it does not persist a global shared plan.
Options expire from a bounded in-process registry (128 options); re-evaluate after restart/expiry.
For Python reuse, carry forward the returned effective scenario and applicable edit history.
Appointment windows are visit-specific: enforced in eligibility and checked again at output.
Overtime is capped at 120 additional minutes per crew-day by default; overrides may lower that cap.
All costs are incremental to the supplied current plan. Existing roster labor is assumed fixed.

`ApproveResult.effective_scenario` preserves approved crew availability and current bookings.
The HTTP API still loads named scenarios and does not persist approval sessions. Do not send only
`new_current_plan` back against an unchanged roster after adding capacity. Python callers can reuse
the effective scenario; HTTP approval chaining is deferred. Appointment windows remain in the
approved option's edit history and must be reapplied to future analyses.

Recovery action lists may omit overtime/temporary capacity when the bounded search finds no
validated operational improvement over both no action and rebalance. Render returned options;
do not assume all three action kinds are present. Cost or option IDs alone do not establish benefit.

### Lane R integration fixes (2026-09-26, no schema change)

These notes supersede the earlier notes above where they differ.

- **Now.** The earliest date a disruption changes, or the earliest booking it breaks, is "now".
  Current-plan visits before now come back with `locked: true` and state `locked` in every option.
  Crew-days before now keep only the minutes their booked visits used, so no option adds a visit
  in the past. Evaluate rejects `move_visit` into the past, moving a past visit, and
  `extend_crew_day` or `add_crew_day` before now, with a 422 that names the date ("Thu 14 Jun").
- **Interventions.** Evaluate rejects disruption kinds in `interventions` with a 422.
  `move_visit` checks the target crew's skill and cluster ("Crew IA does not do battery days.").
  `add_crew_day` allows at most one normal day of minutes and cannot re-add a crew the disruption
  removed on that date.
- **Options.** Overtime and temporary capacity start from now, skip crew-days the disruption cut,
  and never land on a day with no working crew. A paid option stays unless another returned option
  misses no more deadlines at no more modeled cost and wins on one. Rebalance that equals no action
  is labeled "Rebalance existing crews: same plan as no action". Ties for Lowest modeled cost go to
  no action. Labels use human dates ("Add temporary crew TEMP-BA on Fri 15 Jun").
- **Counts and economics.** `deadlines_recovered` is no-action misses minus this option's misses,
  never below 0. `cost_per_deadline_recovered_usd` is the cost above no action over deadlines
  recovered, never below 0. The deadline penalty line is never below 0. `temporary_crew_day`
  follows `hourly_wage` × `crew_size` × 8 h unless set directly. Overrides have bounds, and
  `crew_size` and `max_overtime_min` must be whole numbers. Infeasible options report no changes.
- **Solver.** Recovery budgets count deterministic solver time, so the same request returns the
  same option IDs and plans in every run. Price-only changes reuse solved plans. A result that is
  not proven best has `proven_optimal: false` and a message that starts "Best found".
- **Approval.** Approve compares plan content without `solve_ms`, `stages`, `message`, and
  `lowest_modeled_cost`, so an older issue of the same option still approves. After approval,
  this server accepts `new_current_plan` as `current_plan`, including added temporary crews and
  overtime, until it restarts. Approved overtime counts against the per-crew-day cap through the
  config parameters `overtime_granted:<crew>:<date>`.
