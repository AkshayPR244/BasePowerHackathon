# Contracts

Rollout Planner is a planning and recovery analysis tool for residential battery installers. It takes an installation plan plus a disruption (crew out, late shipment, slipped approval), finds the best recovery, and explains what is at risk and why.

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
