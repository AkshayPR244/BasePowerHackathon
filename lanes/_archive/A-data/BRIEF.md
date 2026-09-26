# Lane A · Data, Valuation, Truth

## Mission
Rollout Planner is a planning and recovery analysis tool for residential battery installers. It takes an installation plan plus a disruption (crew out, late shipment, slipped approval), finds the best recovery, and explains what is at risk and why.

Lane A gives every other lane inputs it can trust and a validator that tells the truth about any plan or recovery.

## Current state
- Delivered: frozen contracts in `backend/app/contracts/`, empty lane packages, the tiny fixture inputs in `data/demo/tiny/`, and its expected responses in `data/demo/tiny/expected/*.json`.
- Not delivered: the scenario loader, the validator, contract tests. You build them.

## Owns
- `backend/app/data/`
- `backend/app/valuation/`
- `backend/app/validate/`
- `data/` (except `data/demo/tiny/expected/`, which changes only with a human)
- `backend/tests/lane_a/`
- `backend/tests/contract/` (you create it. Other lanes may add files to it, not edit yours)
- `lanes/A-data/`

## Must not touch
- `backend/app/contracts/` (additive changes only, per `docs/CONTRACTS.md`)
- `backend/app/planning/`, `baselines/`, `compare/`, `api/`, `backend/tests/lane_b/`
- `frontend/`, `scripts/`
- The validator must never import `app.planning` or `app.baselines`. You write a test that enforces this (A-03).

## Inputs
- `docs/SPEC.md` sections 4, 5, 6, 8, 13.
- `backend/app/contracts/models.py`, `enums.py`, `units.py`, `hashing.py`.
- `data/demo/tiny/`: `scenario.yaml`, `sites.csv`, `sites.geojson`, `clusters.geojson`, `crew_days.csv`, `inventory.csv`, `current_plan.csv`.
- `data/demo/tiny/expected/*.json`: computed by a throwaway exhaustive enumerator. Unique optimum in each case.

## Outputs (interfaces other lanes import)
- `app.data.load.load_scenario(scenario_id) -> Scenario`. Sets `scenario_hash` with `app.contracts.hashing.scenario_hash`. Raises `ScenarioLoadError(issues: list[InputIssue])`.
- `app.data.load.scenario_ids() -> list[str]` and `summarize(scenario) -> ScenarioSummary`.
- `app.validate.validate_plan(scenario, result) -> ValidationReport`. Lane B calls it on every plan. The scenario passed in already has the result's edits applied. Keep this signature once it lands.
- `app.valuation.value_table.value_table(scenario) -> list[ValueTableRow]`, cached by input hash.
- `data/demo/standard/` scenario and `data/manifests/*.json`.

Ship the loader and a `validate_plan` that returns `ValidationReport(checked=False, valid=False, validator="stub")` in your first PR. Lane B imports both. Then replace the validator body.

## Files to create
| File | Purpose |
|---|---|
| `app/data/load.py` | Scenario directory to `Scenario`. CSV lists use `;` |
| `app/data/validate_inputs.py` | Input checks that return `InputIssue`s |
| `app/data/generate_standard.py` | Seeded synthetic "standard" scenario writer |
| `app/data/manifest.py` | Build and write `Manifest` JSON with sha256 |
| `app/data/prepare_ercot.py` | NP6-785-ER 2018 load-zone prices to `prices.parquet` |
| `app/data/prepare_hcad.py` | Bounded HCAD GeoJSON query, anonymized (P2) |
| `app/validate/plan.py` | Independent validator |
| `app/validate/enumerate_tiny.py` | Exhaustive enumerator for tiny cases |
| `app/valuation/battery.py` | HiGHS battery MILP (SPEC section 6) |
| `app/valuation/value_table.py` | `value(site_id, install_date)` table plus cache |
| `tests/contract/test_fixtures_roundtrip.py` | Every fixture and expected JSON round-trips through the models |
| `tests/contract/test_boundaries.py` | AST check: `app/validate` never imports planning |

## Loader notes
- `scenario.yaml` holds `ScenarioConfig` fields plus `travel_allowance_min: {cluster_id: minutes}`. Pop that key before validating the config.
- `Site.lon/lat` come from the `sites.geojson` point (polygon: mean of the ring).
- `Cluster.outline` comes from `clusters.geojson`. `travel_allowance_min` comes from the YAML.
- `skills` and `allowed_clusters` are `;`-separated. Parse to sorted lists.
- The expected JSON `scenario_hash` values must equal `scenario_hash(load_scenario("tiny"), plan.edits)`. If they differ, your loader output differs from the one used to build them. Fix the loader, not the expected files.

## Scope

### P0 (vertical slice first)
1. Scenario loader for `data/demo/tiny` into contract models. Validator stub with the final signature.
2. Contract tests: round-trip the tiny scenario and every `expected/*.json`. Hashes match. Boundary test.
3. Validator: recompute every hard constraint from assignments and scenario inputs. One `ValidationIssue` per violation. Set `checked=True`. Recompute `ObjectiveComponents` and flag `OBJECTIVE_MISMATCH`.
4. Tiny enumerator: reproduce the objectives in `data/demo/tiny/expected/` for strict, strict with Crew A out Monday (infeasible), and recovery with Crew A out Monday.
5. Input validation with structured errors: duplicate IDs, unknown foreign keys, non-finite or negative numbers, date order, duplicate planned installs, contradictory locks. A ready date after a deadline is a valid infeasible case, not a parse error. Surface contradictory locks. Never drop them.
6. Synthetic standard scenario: 30 jobs, 3 clusters, 3 crews, 10 working days, fixed seed. `synthetic: true` plus a `synthetic` provenance note. Same seed gives the same bytes.

### P1
7. ERCOT NP6-785-ER 2018 load-zone prices to `data/demo/standard/prices.parquet` with a manifest. Fallback: gridstatus. Last resort: labeled synthetic prices. Never fill missing intervals.
8. Battery valuation MILP per SPEC section 6 with the full test list.
9. Value table `value(site_id, install_date)`, cached by input hash under `data/cache/`. Solver status per row.

### P2
10. HCAD bounded GeoJSON query as a `standard_real` scenario. Anonymous IDs. No owner names or addresses.
11. Load-limited valuation sensitivity with ResStock profiles.

## Definition of done
- The loader reads tiny and standard. Contract tests pass.
- The validator catches one deliberately broken plan per `ViolationCode` and passes every expected tiny plan.
- The tiny enumerator agrees with every expected objective.
- Every prepared dataset has a manifest in `data/manifests/`.
- `make check-a` passes (planned target. Until it exists: `cd backend && uv run ruff check app/data app/valuation app/validate && uv run pytest -q tests/lane_a tests/contract`).

## Cut list (cut in this order)
1. ResStock load-limited sensitivity.
2. HCAD real parcels (keep synthetic geometry).
3. gridstatus fallback (go straight to labeled synthetic prices).
4. Value table cache (recompute each time).
Never cut the loader, the validator, or the tiny enumerator.

## Working rules
- Pull `origin/main` at session start. Open a small PR to main with `gh pr create` when your check passes and a P0 item lands. Do not merge it yourself. A-01 is the first PR. Lane B waits on it.
- Update `lanes/A-data/PROGRESS.md` after every feature. Write requests to other lanes in `lanes/<their lane>/NEEDS.md`.
