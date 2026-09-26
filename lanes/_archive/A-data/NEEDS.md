# Requests to Lane A

## From Lane B (2026-09-26)
- **Need:** `app.data.load.load_scenario(scenario_id) -> Scenario` and `app.data.load.scenario_ids() -> list[str]`.
- **Until then:** Lane B reads fixtures with `backend/app/api/fixture_loader.py`. `app/api/scenarios.py` switches to your loader as soon as `app.data.load` imports. Lane B deletes the stand-in after your A-01 merges.
- **Need:** `app.validate.validate_plan(scenario, result)`. Lane B passes the scenario with the result's edits already applied (`app.planning.edits.apply_edits`).
- **Need:** `data/demo/standard/` (30 jobs, 3 clusters, 3 crews, 10 working days, fixed seed, labeled synthetic). It unblocks Lane B's B-16.
- **Need:** `app.valuation.value_table.value_table(scenario) -> list[ValueTableRow]`. Lane B already calls it when it imports. Rows need `solver_status == "optimal"` to count. Lane B labels other rows as unresolved $0.
