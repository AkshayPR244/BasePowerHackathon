# SlackLine

**A public-data prototype for scheduling residential battery deployments and explaining recovery decisions.**

Given candidate properties, installation resources, and stated commitments, produce a feasible crew-day schedule. Prefer schedules that meet deadlines; among equally good commitment outcomes, maximize modeled operating margin after commissioning; then reduce travel. Let an operator change a resource, compare plans, and inspect why jobs moved or remained unscheduled.

**Status:** Implementation specification. The application, commands, and acceptance results below are planned, not already implemented. Update this section and verify every quick-start command before submission.

**Track:** Most Commercializable. Public ERCOT data supports the valuation experiment; this is not a live trading or booking system.

## 1. What we are demonstrating

The prototype combines public geographic and energy data with explicit operational benchmark assumptions. It does not require Base customer records, credentials, or integrations.

We aim to demonstrate:

1. A schedule that respects the modeled resource and eligibility constraints.
2. Measurable comparison with understandable scheduling baselines.
3. Recovery after a crew, inventory, or readiness change.
4. Traceable explanations of selection, deferral, and plan changes.
5. An experiment showing when price-aware commissioning improves the result—and when it does not.

Public properties are candidate locations, not confirmed customers. Crew counts, job durations, readiness, deadlines, and inventory are published benchmark inputs. ResStock profiles are modeled loads. Historical-price optimization is a hindsight upper-bound benchmark, not a forecast of achievable earnings.

## 2. Scope and decisions

| In the MVP | Out of scope |
|---|---|
| 30 candidate jobs; configurable up to 100 for experiments | Statewide operational deployment |
| One study area with three geographic clusters | Exact road-route sequencing |
| Three crews and ten working days | Multi-visit installation workflows |
| One fixed battery configuration | Battery hardware design or electrical approval |
| CSV/Parquet/GeoJSON snapshots | Live ERP, CRM, market, or booking integrations |
| Deadlines, readiness, crew skills, inventory, locked appointments | Acquisition/conversion prediction |
| Precomputed site/date operating values | Reinforcement learning or live dispatch |
| Map, calendar, inspector, plan comparison, export | Authentication, Kubernetes, event streaming |

One job represents a single remaining installation work package. No job crosses a working-day boundary. Installation duration includes the modeled onsite commissioning work; any later qualification delay is a separate scenario parameter.

Use one geographic cluster per crew-day and a fixed conservative travel allowance per active crew-day. Label this approximation in the UI. Do not draw calculated routes or claim road-level feasibility without implementing a routing model.

Utility program milestones are a stretch feature. The MVP keeps a program label for filtering but does not claim to model contractual capacity acceptance.

## 3. User workflow

1. Load a bundled scenario and inspect provenance and assumptions.
2. View the existing plan or generate a baseline.
3. Solve the strict plan: all jobs completed by their deadlines.
4. If strict feasibility fails, explicitly offer recovery mode.
5. Remove a crew-day, delay inventory, or change a ready date.
6. Re-solve and compare with the immutable baseline.
7. Inspect a deferred job; test its forced inclusion or an added resource.
8. Export assignments, missed commitments, assumptions, and solver status.

Nothing in the application sends messages or changes external appointments.

## 4. Public data and provenance

| Input | Source | Preparation |
|---|---|---|
| Candidate property geometry and selected attributes | [Houston HCAD parcel service](https://mycity2.houstontx.gov/pubgis02/rest/services/PDD/HCAD_Parcels/MapServer/0) | Select residential parcels, assign anonymous IDs, retain a reproducible spatial sample |
| Historical settlement prices | [ERCOT NP6-785-ER](https://www.ercot.com/mp/data-products/data-product-details?id=np6-785-er) | Extract the relevant load-zone series, normalize timestamps and units |
| Optional household load shapes | [ResStock](https://resstock.nlr.gov/datasets), [public access](https://registry.opendata.aws/nrel-pds-building-stock/) | Select a small set of documented AMY residential profiles |
| Optional roads | [Geofabrik Texas](https://download.geofabrik.de/north-america/us/texas.html) | Crop and cache a study-area extract; optional for the cluster-based MVP |
| Resources and commitments | Versioned scenario configuration | Explicit assumptions with fixed seeds for generated cases |

The sources have been identified; sample downloads, schema compatibility, and joins must be verified during implementation. Do not make large full-state downloads the critical path. HCAD supports bounded GeoJSON queries; use these before adding a separate footprint dataset.

Recommended energy replay: an eight-week window using 2018 ERCOT prices, with the first two weeks available for installations. If loads are used, pair them with AMY 2018 profiles. Current parcel geometry plus historical energy data is a constructed benchmark, not a historical reconstruction. Confirm archive availability before freezing dates.

Every prepared dataset gets a manifest containing source URL, release/version, retrieval date, covered dates, license/redistribution notes, SHA-256, transformation summary, and row counts. Separate observed, modeled, derived, and assumed fields. Do not include owner names or mailing addresses in the demo export.

All core demo inputs are cached locally. Network failures must not prevent solving or inspecting the calendar. Check redistribution terms before publishing source-derived files; otherwise publish preparation scripts and an independently constructed fallback fixture.

## 5. Input contract

Use CSV for small operational tables, Parquet for time series, GeoJSON for map geometry, and YAML for scenario configuration. All IDs are strings. Durations are integer minutes. Energy is kWh, power is kW, prices are USD/MWh, value is USD. Display rounded values only; calculate at full precision.

| File | Required fields |
|---|---|
| `sites.csv` | `site_id`, `cluster_id`, `program_id`, `ready_date`, `deadline`, `duration_min`, `required_skill`, `configuration_id`, `load_zone`, optional `profile_id` |
| `sites.geojson` | Geometry plus matching `site_id`; no financial or scheduling logic |
| `crew_days.csv` | `crew_id`, `date`, `available_min`, `skills`, `allowed_clusters` |
| `inventory.csv` | `configuration_id`, `available_date`, `quantity` |
| `appointments.csv` | `site_id`, `crew_id`, `date`, `locked` |
| `prices.parquet` | `timestamp_utc`, `interval_hours`, `load_zone`, `price_usd_mwh` |
| `loads.parquet` (optional) | `timestamp_utc`, `interval_hours`, `profile_id`, `load_kw` |
| `scenario.yaml` | Planning/evaluation dates, timezone, battery parameters, travel allowances, qualification lag, solve limits, objective mode, provenance references |

`skills` and `allowed_clusters` use documented semicolon-delimited IDs in CSV, parsed to sets. Inventory rows are incoming quantities, not cumulative balances. Ready date is inclusive; deadline is the latest permitted installation day. Include every deadline within the planning horizon for the standard benchmark.

Validate duplicate IDs, foreign keys, finite numbers, units, date ordering, duplicate appointments, and missing time-series intervals. A ready date after a deadline is a valid infeasible planning case, not a parser failure. Contradictory hard locks must be surfaced, not silently dropped.

Scheduling dates use `America/Chicago`. Energy timestamps are timezone-aware UTC. Respect source interval-ending conventions and daylight-saving indicators. Never merge ambiguous local timestamps or silently fill missing prices. Align load/price interval boundaries explicitly and report rejected rows.

## 6. Battery valuation contract

Keep valuation independent of scheduling. It produces a table `value(site_id, install_date)` plus traceable dispatch diagnostics. Cache by profile, configuration, zone, commissioning timestamp, evaluation horizon, and input hashes.

For each candidate date, operation begins on the first modeled energy interval after installation-day completion and the configured calendar-day qualification lag. This is a scenario assumption, not evidence that wholesale participation starts immediately after installation.

For each interval t, use nonnegative charge and discharge power c[t], d[t], and stored energy E[t]:

```text
E[t+1] = E[t] + eta_charge * c[t] * dt - d[t] * dt / eta_discharge
reserve_kwh <= E[t] <= capacity_kwh
0 <= c[t] <= charge_limit_kw
0 <= d[t] <= discharge_limit_kw
margin = sum(price_usd_mwh[t] / 1000 * (d[t] - c[t]) * dt)
```

Prevent simultaneous charging and discharging explicitly with a binary mode variable. Do not assume prices are always positive or that losses alone prevent artificial cycling. Keep interval units consistent.

MVP initial and terminal energy both equal the configured reserve. Only energy above reserve is traded. This establishes a comparable operating-margin benchmark without monetizing free initial stored energy. It excludes the cost of establishing the commissioning reserve, hardware, and acquisition; do not label the result lifetime profit or total ROI.

Two explicit valuation modes:

- **Unrestricted-export benchmark:** identical batteries in one price zone have identical values for the same commissioning date. Household load is unnecessary.
- **Load-limited sensitivity:** constrain discharge to modeled household demand (or demand plus a stated export allowance). Wholesale-valued load offset remains a benchmark assumption, not a retail-bill calculation. ResStock profiles are archetype assignments, not measured consumption at those parcels.

Start with unrestricted export. Add load-limited sensitivity only after the end-to-end scheduler works. Do not introduce unsupported site differences just to create a more dramatic ranking.

Use a common evaluation end date and terminal-energy condition for all commissioning dates. Battery schedules must be feasible over continuous time, not independent daily maximizations that reset stored energy. Record dispatch solver status; an unresolved valuation solve cannot silently become an exact objective coefficient.

## 7. Scheduling model

Let x[i,d,r] be a binary assignment of job i to day d and crew r. Let y[r,d,k] indicate crew r working in cluster k on day d. Generate only assignments compatible with skill, geography, readiness, and calendar availability.

Hard constraints:

1. Each job is assigned at most once; exactly once in strict mode.
2. Each crew-day serves at most one cluster.
3. Assigned jobs imply the corresponding cluster selection.
4. Onsite minutes plus the active cluster travel allowance do not exceed available crew minutes.
5. Cumulative equipment consumption by each date does not exceed cumulative receipts.
6. Locked assignments remain fixed.
7. No pre-commissioning energy value is credited.

### Strict mode

Require every job to finish by its deadline. Maximize total precomputed operating value, then minimize changes to unlocked appointments, then minimize travel allowance used. If all site/date values are zero or equal, report that energy valuation did not distinguish those choices.

### Recovery mode

Relax completion/deadline commitments only; retain resource, readiness, inventory, and lock constraints. Optimize lexicographically:

1. Minimize count of jobs late or unscheduled.
2. Minimize aggregate delay: assigned jobs use days past deadline; unscheduled jobs use a declared penalty larger than any within-horizon lateness.
3. Maximize operating value; unscheduled jobs contribute zero.
4. Minimize changed existing appointments.
5. Minimize travel allowance used.

The objective order is a published benchmark policy. Implement sequential solves, fixing achieved higher-priority objectives within documented numerical tolerance. Do not claim a proven lexicographic optimum if an earlier solve timed out. Return stage-level status, incumbent, gap, and elapsed time. Use a total solve-time budget, not an unlimited budget per stage.

If locks themselves make the problem impossible, recovery can remain infeasible. Explain that additional user changes are necessary; do not discard locks automatically.

## 8. Baselines and evidence

Implement earliest-deadline-first and nearest-cluster-first baselines. They use the same candidate data, travel model, eligibility rules, inventory, horizon, and valuation table. Both produce assignments passed through the same independent validator.

Also solve a deadline-and-travel-only variant. Revalue its output using the same battery model to measure the incremental contribution of ERCOT-aware scheduling. This comparison may show no improvement; report that result.

Public geography and energy data establish realistic inputs. They do not establish customer interest, operational savings, or achieved revenue. Evidence should distinguish:

- **Correctness:** independent constraint validation.
- **Optimization quality:** tiny-case exhaustive search and solver gaps.
- **Benchmark performance:** objective comparisons across fixed cases.
- **Product usefulness:** inspectable recovery workflow; requires later user validation.

If full routing is added later, [Solomon instances](https://www.sintef.no/projectweb/top/vrptw/solomon-benchmark/) can evaluate that component. Do not claim comparability with published routing results for our different cluster-based model.

## 9. Explanations and counterfactuals

Hard blockers come from explicit data checks: missing readiness, incompatible crew skill, or no legal date. A tight resource constraint alone is not proof of the reason a job was deferred.

For an eligible deferred job, offer “include by deadline.” Add that requirement and re-solve against the same scenario. Show feasibility, displaced jobs, commitment changes, value change, and solve status. Cache this result by plan and intervention; run it only on request.

Offer “add a crew-day” and “restore inventory date” with the same mechanism. Explain that these interventions change feasibility under modeled assumptions. Do not invent causal diagnoses or dollar savings beyond the actual objective.

## 10. UI contract

One desktop workspace:

- **Header:** scenario name, data provenance badge, planning dates, objective policy, solve status.
- **Metrics:** on-time/late/unscheduled jobs, modeled operating margin, crew utilization, moved appointments.
- **Map:** properties and clusters, linked to selected jobs; labels/icons as well as colors.
- **Crew calendar:** one row per crew; daily assignments and capacity usage; locked appointments visibly marked.
- **Deferred list:** all unscheduled or blocked jobs remain visible.
- **Inspector:** readiness, requirements, evidence source, reason, and counterfactual actions.
- **Compare panel:** baseline versus scenario and explicit changes.

Editing marks the result stale. Keep the previous plan visible with a “previous result” label until re-solving completes. Only accept a response matching the current scenario revision; discard late responses from older requests. The baseline is immutable until explicitly replaced.

Render local geometry without requiring map tiles. If tiles are enabled, failure must leave the calendar and geographic outline usable. Download exports as JSON plus CSV; no external writes.

## 11. Architecture

```text
Public-source preparation → validated local snapshot
Local snapshot → battery valuation cache → scheduling model
Scheduling result → independent validator → explanations/comparison → API/UI
```

Recommended stack: Python 3.12, uv, FastAPI, Pydantic, pandas/PyArrow, SciPy/HiGHS; React, TypeScript, Vite, and a lightweight map/chart library. Pin working dependencies in lockfiles. Run locally without authentication or a database.

Suggested layout:

```text
backend/app/
  schemas.py
  ingest.py
  valuation.py
  planning.py
  validate_plan.py
  baselines.py
  compare.py
  api.py
frontend/src/
  api/
  components/
  views/
scripts/prepare_data.py
data/manifests/
data/demo/
tests/
README.md
```

These are responsibility boundaries, not a requirement to force all logic into eight files. Split a module when it owns unrelated concerns; avoid arbitrary line-count rules or elaborate abstractions. Keep solvers and validators callable without FastAPI. The validator recalculates resource use from assignments rather than calling the model's constraint-construction helpers.

### API surface

- `GET /api/scenarios`: bundled scenario summaries.
- `GET /api/scenarios/{id}`: validated inputs and provenance.
- `POST /api/plans`: scenario plus edits, mode, and revision; returns validated result or structured error.
- `POST /api/plans/compare`: compare two retained local results.
- `POST /api/plans/counterfactual`: explicit intervention against an identified scenario revision.

For this scale, bounded request/response solves are sufficient; execute CPU work outside the async event loop. Disable duplicate solve submissions. No task queue is required. Store local snapshots and use content hashes for reproducibility.

Every result includes `scenario_hash`, `revision`, `mode`, `status`, stage-level solver metadata, assignments, unscheduled jobs, objective components, validation result, and assumptions. Never serialize NaN/infinity or return invalid assignments as a successful plan.

## 12. Planned quick start

These are target commands to implement, not commands for an existing application:

```bash
make setup          # install pinned Python and frontend dependencies
make prepare-demo   # validate bundled demo; raw downloads are a separate opt-in command
make dev            # start backend and frontend
make check          # formatting/lint, types, focused tests, frontend build
make demo           # reset to the recorded baseline scenario
```

The default demo needs no API keys and no network after dependency installation. Provide `.env.example` for paths, ports, and solver limits only. Include exact supported commands, ports, and troubleshooting once implemented. An optional source-preparation command must pin versions and emit a manifest; it must not run automatically at app startup.

## 13. Acceptance criteria

### Core behavior

- All displayed plans pass independent validation.
- Strict infeasibility is distinguished from timeout without an incumbent.
- Recovery mode never silently relaxes resource or lock constraints.
- Removing a crew-day, delaying inventory, and changing readiness each produces reproducible comparisons.
- A missing approval cannot be bypassed by adding a crew.
- Valuation and scheduling can be reproduced from saved inputs without the UI.

### Focused verification

- Tiny scheduling instance checked by exhaustive enumeration.
- Battery energy conservation, power limits, no simultaneous cycling, consistent boundary energy, and negative-price case.
- Inventory timing, qualification delay, hard locks, zero capacity, and impossible deadline cases.
- Baselines checked by the same independent validator.
- Identical sites in one zone produce identical same-date values.
- One UI end-to-end test: load → edit crew availability → solve → inspect comparison → export.

Aim for cached 30-job replanning within five seconds on the demo laptop, with a hard configurable time limit (initially 15 seconds). These are performance targets, not measured claims. Precompute battery valuations before the live demo and report their preparation time separately. Do not hide invalid or timed-out runs when reporting results.

## 14. Build order and demo

1. Freeze schemas, units, objective order, and a tiny fixture.
2. Build the scheduler and independent validator with equal site values.
3. Load a small real parcel subset and build the calendar/map loop.
4. Add ERCOT ingestion and physically consistent valuation; cache coefficients.
5. Add baselines, recovery comparison, and one forced-inclusion explanation.
6. Polish, measure, document provenance, and record the demo.

Cut optional load profiles, road routing, utility milestones, and vision before cutting validation or explanation. Keep a geometry-only offline map fallback.

Three-minute demo: show provenance and baseline; remove a crew-day; identify threatened commitments; compare recovery options; inspect one deferred site; show baseline versus optimized operating value; export the plan. Explicitly state whether the energy-aware objective changed the schedule in this case.

## 15. Submission and limitations

Include a public repository, verified quick start, architecture description, data manifests, assumptions, known limitations, a 2–5 minute Loom video, a working-app capture or deployed URL, and team names/roles/contacts.

Known limitations: constructed demand and resources; representative rather than measured household profiles; simplified travel and single-stage jobs; assumed qualification lag; no live integrations; hindsight prices; gross operating margin rather than total business profit; no evidence that Base lacks equivalent internal tools.

Suggested pitch: **“SlackLine turns a public-data deployment scenario into a feasible installation plan, explains the consequences of disruptions, and measures when earlier commissioning creates additional modeled energy value.”**
