# Synthetic scenario suite

Ten valid, fixed-seed portfolios for live planner, recovery, API and UI testing. Every initial current plan is solved in strict mode and independently validated before publication. No hand-authored schedules or intentionally malformed cases are registered.

## Generate and run

```bash
cd backend
uv run python -m app.data.generate_scenarios --all
uv run python -m app.data.generate_scenarios --scenario crew_out_recoverable
cd ..
make dev-live
```

Use **Live API** mode. The selector discovers scenario folders via the unchanged `/api/scenarios` endpoint. Select a suite scenario to see its healthy strict plan and bold, collapsible **Scenario briefing** banner. Apply primary disruption to send the explicit preset through the existing edit and recovery contracts; use Reset demo to restore the healthy state. Balanced small has Analyze healthy baseline instead. Value sensitive also offers Compare objective policies after applying its primary disruption.

The briefing shows situation before the primary edit, then trigger/question only while that exact preset is active. What to watch sits next to options; the success criterion sits next to approval. Truth labels remain visible when the banner is collapsed. Missing report metadata renders no invented story; operational controls and scenario loading remain usable. Non-primary edits do not display a misleading primary-trigger story.

## Design and provenance

- `backend/app/data/generate_standard.py`: shared typed `Spec` and `CrewSpec`, deterministic single-worker CP-SAT healthy-plan generation; extended rather than copied ten times. Existing standard/tiny ground truth and validators are unchanged.
- `backend/app/data/scenario_suite.py`: fixed seeds, parameterized portfolio specs and typed disruption recipes. Recipes select concrete visits/receipts from the solved current plan with stable sorting.
- `backend/app/data/generate_scenarios.py`: staging outside discovery, copying real prepared Parquet files, independent current-plan validation, operational manifests and generated frontend edit presets.
- `frontend/src/scenario-presets/*.json`: generated numeric/ID API edits only. This is separate from narrative prose.
- `frontend/src/narratives/reports.json`: static, typed, frontend-only editorial reports keyed by scenario ID. They are authored separately and byte-stable across generation, never read by the backend loader, planner, validator, or API and never included in request bodies. They do not represent a CRM feed. Regeneration intentionally leaves this registry unchanged; tests enforce exact ID coverage.
- Each demo folder has scenario YAML, site CSV/GeoJSON, closed cluster polygons, visits, crew days, dated inventory receipts, solved current plan and byte-identical copies of the prepared standard price/load Parquet files. Original energy source manifests and provenance are retained. Each synthetic operational file has a content-hashed manifest in `data/manifests/`.
- Synthetic Houston-area homes are not real customers. Portfolio, appointment, crew, weather-impact and cost assumptions are synthetic/modeled. Prices are observed 2018 data; copied loads are modeled archetypes. No observed weather event is used for these stories.
- YAML parameters record the full typed generator specification plus seed, crew mix/territory, workday, travel, readiness/deadlines, duration choices, receipt cadence, gap/locks, battery/reserve/efficiency, qualification lag, objectives, solver settings and weather assumptions. Incoming receipts are not cumulative balances.
- Same seed and pinned dependency versions regenerate identical input bytes, scenario hash and current plan. Single-worker deterministic work limits govern generation. Runtime recovery is still bounded by wall-clock budgets; exact runtime option lists are not claimed reproducible or exhaustive.

## Cases

All initial healthy strict results must have an incumbent, independent validation and every home on time. Status may be optimal or feasible depending on solve completion; infeasible and no-incumbent are not accepted healthy results.

### `balanced_small` — seed 101

**Story:** A normal operating week. **Operator:** Dispatch manager.

**Initial condition:** A small synthetic portfolio has room between commitments. Start by checking that every home can finish on time. 12 homes, 8 commitment-window business days and 2 overflow days.

**Decision question:** Does the schedule leave enough room for routine operational variation?

**Named disruption payload:**

```json
[]
```

**Expected disrupted strict:** feasible (on time). **Recovery class:** recoverable.

All 12 homes stay on time with under 40% aggregate utilization. No disruption is needed; Analyze healthy baseline exposes the no-action comparison.

**UI demonstration:** On-time commitments and spare crew capacity; The separate install and battery visits.

**Success criterion:** Compare only validated outcomes that respect inventory, skills, territories, readiness, appointments and visit precedence.

### `tight_feasible` — seed 102

**Story:** Find the last safe margin. **Operator:** Capacity planner.

**Initial condition:** A busy portfolio shares a tightly loaded battery crew. The original commitments are achievable. 30 homes, 7 commitment-window business days and 2 overflow days.

**Decision question:** Can the team recover without exceeding its remaining capacity?

**Named disruption payload:**

```json
[
  {
    "kind": "remove_crew_day",
    "crew_id": "BA",
    "date": "2018-06-05"
  }
]
```

**Expected disrupted strict:** infeasible. **Recovery class:** recoverable.

30 homes are strict-feasible; battery crew utilization through the latest deadline exceeds 85%. Aggregate utilization includes install slack and overflow and is lower. Removing the busiest battery day makes strict planning infeasible; eligible temporary capacity can protect all commitments.

**UI demonstration:** Battery crew utilization before the deadline; Late or deferred work after capacity is removed.

**Success criterion:** Compare only validated outcomes that respect inventory, skills, territories, readiness, appointments and visit precedence.

### `crew_out_recoverable` — seed 103

**Story:** Protect commitments after a crew absence. **Operator:** Dispatch manager.

**Initial condition:** The undisrupted schedule has assigned install and battery crews to every synthetic home. 24 homes, 8 commitment-window business days and 2 overflow days.

**Decision question:** Which recovery protects commitments with the least appointment disruption?

**Named disruption payload:**

```json
[
  {
    "kind": "remove_crew_day",
    "crew_id": "IA",
    "date": "2018-06-07"
  }
]
```

**Expected disrupted strict:** feasible (on time). **Recovery class:** recoverable.

The named high-load install crew-day is lost. No action moves installs and battery work; rebalancing finds a validated on-time option.

**UI demonstration:** Directly affected installs and their battery visits; No action versus rebalancing or useful extra capacity.

**Success criterion:** Compare only validated outcomes that respect inventory, skills, territories, readiness, appointments and visit precedence.

### `inventory_delay_recoverable` — seed 104

**Story:** The battery delivery slips. **Operator:** Inventory coordinator.

**Initial condition:** Battery receipts arrive in dated batches sized to the healthy plan. 18 homes, 8 commitment-window business days and 2 overflow days.

**Decision question:** Can battery visits be reshuffled around the actual receipt date?

**Named disruption payload:**

```json
[
  {
    "kind": "delay_inventory",
    "configuration_id": "B13",
    "from_date": "2018-06-04",
    "to_date": "2018-06-07",
    "quantity": null
  }
]
```

**Expected disrupted strict:** feasible (on time). **Recovery class:** recoverable.

Delay crosses the earliest booked battery visit, so affected battery visits and reschedules must be nonzero. Strict replanning and an on-time recovery remain feasible.

**UI demonstration:** Battery visits displaced by the delayed receipt; Skills on any temporary capacity offered.

**Success criterion:** Compare only validated outcomes that respect inventory, skills, territories, readiness, appointments and visit precedence.

### `readiness_appointment` — seed 105

**Story:** Respect when homes can host work. **Operator:** Scheduling coordinator.

**Initial condition:** The healthy schedule assumes each synthetic home is ready and available for its visits. 12 homes, 8 commitment-window business days and 2 overflow days.

**Decision question:** What can still be achieved while honoring both availability constraints?

**Named disruption payload:**

```json
[
  {
    "kind": "change_ready_date",
    "site_id": "W-01",
    "ready_date": "2018-06-06"
  },
  {
    "kind": "change_appointment",
    "job_id": "W-01-B",
    "available_from": "2018-06-07",
    "available_to": "2018-06-07"
  }
]
```

**Expected disrupted strict:** feasible (on time). **Recovery class:** recoverable.

Readiness is inclusive. The named battery visit must land on the exact available_from/available_to date if scheduled. An on-time recovery exists.

**UI demonstration:** Readiness date and the explicit appointment window; No work before readiness or outside the window.

**Success criterion:** Compare only validated outcomes that respect inventory, skills, territories, readiness, appointments and visit precedence.

### `skill_cluster_bottleneck` — seed 106

**Story:** The right crew, in the right territory. **Operator:** Regional dispatcher.

**Initial condition:** Install and battery crews are assigned to separate North and South territories. 12 homes, 8 commitment-window business days and 2 overflow days.

**Decision question:** Can the affected territory recover without borrowing an ineligible crew?

**Named disruption payload:**

```json
[
  {
    "kind": "remove_crew_day",
    "crew_id": "BN",
    "date": "2018-06-08"
  }
]
```

**Expected disrupted strict:** feasible (on time). **Recovery class:** recoverable.

North and South crews have disjoint territories and install/battery skills. The lost battery day cannot be replaced by the other territory's crew. Eligible rebalancing recovers the work; never assign across skill or territory boundaries.

**UI demonstration:** Crew skill and allowed territory; Useful eligible capacity rather than unsafe substitutions.

**Success criterion:** Compare only validated outcomes that respect inventory, skills, territories, readiness, appointments and visit precedence.

### `two_visit_cascade` — seed 107

**Story:** An install delay reaches the battery visit. **Operator:** Dispatch manager.

**Initial condition:** Each synthetic home needs an electrical install before its battery appointment, with a two-business-day gap. 12 homes, 8 commitment-window business days and 2 overflow days.

**Decision question:** Which downstream battery commitment must change to preserve precedence?

**Named disruption payload:**

```json
[
  {
    "kind": "change_appointment",
    "job_id": "W-01-I",
    "available_from": "2018-06-08",
    "available_to": "2018-06-08"
  }
]
```

**Expected disrupted strict:** feasible (on time). **Recovery class:** recoverable.

Moving the named install past its original battery slot moves both visits under no action. The cascade lists the dependent battery visit. The two-business-day gap remains intact; on-time recovery exists.

**UI demonstration:** The moved install and its dependent battery visit; Business-day gaps, reschedules and missed deadlines.

**Success criterion:** Compare only validated outcomes that respect inventory, skills, territories, readiness, appointments and visit precedence.

### `locked_infeasible` — seed 108

**Story:** A promise that cannot move. **Operator:** Operations lead.

**Initial condition:** The healthy plan is fully booked and every appointment is locked. 12 homes, 8 commitment-window business days and 2 overflow days.

**Decision question:** Can any option honor the locks, or must the operator revise the assumptions?

**Named disruption payload:**

```json
[
  {
    "kind": "remove_crew_day",
    "crew_id": "IB",
    "date": "2018-06-05"
  }
]
```

**Expected disrupted strict:** infeasible. **Recovery class:** locked-infeasible.

Every healthy-plan booking is locked. Removing the named occupied install crew-day makes both strict and all recovery options infeasible. No assignment may silently move or omit a lock. UI shows infeasibility, hides unevaluated economics, and disables approval.

**UI demonstration:** Infeasibility instead of silently moving a lock; Disabled approval when no feasible plan exists.

**Success criterion:** Recognize the infeasible promise; do not approve or silently relax a locked visit.

### `late_overflow` — seed 109

**Story:** Finish the work after promises slip. **Operator:** Operations lead.

**Initial condition:** The original plan finishes inside the commitment window; extra business days are available afterward. 12 homes, 5 commitment-window business days and 4 overflow days.

**Decision question:** How much can be completed in overflow, and which appointments become late?

**Named disruption payload:**

```json
[
  {
    "kind": "delay_inventory",
    "configuration_id": "B13",
    "from_date": "2018-06-04",
    "to_date": "2018-06-11",
    "quantity": null
  }
]
```

**Expected disrupted strict:** infeasible. **Recovery class:** late-but-feasible.

The first receipt moves to June 11, after all June 8 deadlines. Disrupted strict planning is infeasible. Recovery completes all 12 homes in overflow with late battery visits and no unscheduled homes. Added capacity cannot erase lateness before the receipt.

**UI demonstration:** Late jobs completed in the overflow days; No inventory use before receipt and honest reschedule counts.

**Success criterion:** Compare only validated outcomes that respect inventory, skills, territories, readiness, appointments and visit precedence.

### `value_sensitive` — seed 110

**Story:** Compare commissioning order. **Operator:** Planning analyst.

**Initial condition:** The healthy plan meets every commitment. A shared capacity stress test exposes choices between otherwise legal recovery schedules. 12 homes, 8 commitment-window business days and 2 overflow days.

**Decision question:** Does earlier commissioning increase modeled operating margin under identical constraints?

**Named disruption payload:**

```json
[
  {
    "kind": "remove_crew_day",
    "crew_id": "BA",
    "date": "2018-06-13"
  }
]
```

**Expected disrupted strict:** feasible (on time). **Recovery class:** recoverable.

Both policy solves use the same named battery-day removal, hard constraints, current plan and strict mode. Multiple on-time replacements are legal. Value-aware commissioning earns greater modeled margin and produces different assignments than deadline/travel-only. The healthy current plan itself is preserved by both policies because changed appointments precede value in the existing objective order; the shared disruption exposes the tie-break experiment without changing that policy.

**UI demonstration:** Assignment differences between objective policies; Historical-price modeled margin, not forecast profit.

**Success criterion:** Compare only validated outcomes that respect inventory, skills, territories, readiness, appointments and visit precedence.

## Verification

```bash
cd backend
uv run pytest -q tests/scenario_suite
uv run pytest -q tests/lane_a tests/lane_b tests/lane_r tests/contract tests/scenario_suite
uv run ruff check app/data tests/scenario_suite
uv run ruff format --check app/data tests/scenario_suite
uv run python ../scripts/export_openapi.py --check
cd ../frontend
pnpm typecheck
pnpm test
pnpm build
```

Suite tests cover loading and semantic validation, both planning states, recovery classes, independent validation of every option, explicit appointment bounds, useful inventory effects, cascades, disjoint skill/territory crews, overflow completion, lock infeasibility and policy differences. They regenerate every portfolio into a temporary root and compare every file, manifest, hash, current plan and generated preset with the committed version. API listing and recovery are exercised for every ID. Frontend tests cover ID coverage, missing reports and the situation/trigger boundary. See SCENARIO_SUITE_VERIFICATION.md for executed checks and observed results.

## Remaining product limits

This suite does not fix all previously logged integration tasks: runtime past-date freezing and all-crew storm-day handling remain outside this change. These scenarios are synthetic offline replanning exercises and do not claim dispatch against a real-time clock. Approval remains analysis-local; no customers are contacted and no persistent booking system is updated. Suite metrics, calendar, inspector and exports use the selected recovery result consistently. The existing standard demo retains its separate legacy workflow.
