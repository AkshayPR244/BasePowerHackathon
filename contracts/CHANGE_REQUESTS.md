# Contract change requests

The contract in `backend/app/contracts/` is frozen as of the scaffold commit. Full protocol: `docs/CONTRACTS.md`.

- Additive (optional field with a default, new model, new enum member nothing requires): make the change, regenerate types and mocks in the same commit, add one line to the Log.
- Breaking (rename, remove, type or unit change, new required field, changed meaning): add a PROPOSED entry below. Keep working around it. A human decides.

## Log

| Date | Lane | Change | Reason |
|---|---|---|---|
| 2026-09-26 | B | Every error response (400, 404, 405, 422, 500) is an `ApiError`. OpenAPI documents `ApiError` for 400, 404, 422, 500 and no longer lists `HTTPValidationError`. `GET /api/health` adds `values` and `values_seconds`. | The UI handles one error shape. Health reports whether value tables are warm. |
| 2026-09-26 | A | `ScenarioConfig.parameters: list[Parameter] = []` and `ScenarioConfig.weather_rule: WeatherRule \| None = None`. New models `Parameter` (name, value, unit, kind, derivation, source) and `WeatherRule`. Both enter `scenario_hash` only when set, so existing hashes stay valid. | Show every operational number with its tag and source. Weather rule for the replay. |
| 2026-09-26 | A+B | Two visits per home, all optional with defaults. New enum `VisitType` (install, battery_day), new model `Visit`, new `ViolationCode.PRECEDENCE`. New fields: `Site.visits`, `PlannedInstall.job_id`, `ScenarioConfig.min_gap_business_days`, `Assignment.job_id` / `visit_type`, `UnscheduledJob.job_id` / `visit_type`, `PlanChange.job_id` / `visit_type`, `ValidationIssue.job_id`, `ObjectiveComponents.visits_moved` / `customers_to_reschedule`, `DiffSummary.customers_to_reschedule`. **UI note: `assignments` can now contain two entries per `site_id`; key by `job_id ?? site_id`.** The new scenario fields enter `scenario_hash` only when set, so `tiny` hashes are unchanged. | Model the install and the battery day as separate visits with separate crews. See docs/CONTRACTS.md, "Two visits per home". |
| 2026-09-27 | scaffold | Recovery and weather seams (contract 1.2), all additive. New edits `reduce_crew_day`, `change_appointment`, `extend_crew_day`, `pin_visit`, `move_visit` (return invalid_input until lane R). New enums `OptionKind`, `CascadeKind`, `EconomicKind`. New models `RecoveryCounts`, `EconomicLine`, `RecoveryEconomics`, `Explanation`, `CrewLoad`, `RecoveryOption`, `CascadeStep`, `ImpactAnalysis`, `EconomicAssumption`, `RecoveryOptionsRequest`, `RecoveryOptionsResult`, `EvaluateRequest`, `ApproveRequest`, `ApproveResult`, `StormEvent`, `Case`, `SeasonReplayEvent`, `SeasonTotals`, `StressTest`, `SeasonReplay`. New endpoints `POST /api/recovery/{options,evaluate,approve}`, `GET /api/storms`, `GET /api/cases`, `GET /api/season-replay`, all stubbed (`stub: true`, header `X-SlackLine-Stub`). | Freeze the seams so lanes R, C, and W build in parallel. See docs/CONTRACTS.md, "Recovery and weather seams". |
| 2026-09-27 | R | `EvaluateRequest.economics_overrides: dict[str, float] \| None = None`. Generated schemas and types regenerated. | Manual evaluations use the same economic assumptions as options. |
| 2026-09-27 | R | `ApproveResult.effective_scenario: Scenario \| None = None`. | Carries approved capacity, appointment edits (through plan history), and bookings, so temporary resources are not lost in exports. The approval API stays stateless. Callers keep the effective scenario. |
| 2026-09-27 | R | No schema change. Contract seam tests now expect independently validated results for all edits, not unimplemented-edit stubs. Cost ranking includes the canonical no-action option. | The five new edits are implemented. |
| 2026-09-27 | R | No schema change. Paid-capacity options (overtime, temporary capacity) are optional. The engine omits them unless they are operationally better than no action and rebalance. The seam test checks that benefit. Recorded responses regenerated. Lane C notified in NEEDS.md. | Show only options that help. |

## Proposed (waiting for a human)

| Date | Lane | Proposed change | Reason | Affects |
|---|---|---|---|---|
