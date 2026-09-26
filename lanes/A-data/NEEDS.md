# Requests to Lane A

## From Lane B (2026-09-26)
- **Need:** `app.data.load.load_scenario(scenario_id) -> Scenario` and `app.data.load.scenario_ids() -> list[str]`.
- **Until then:** Lane B reads fixtures with `backend/app/api/fixture_loader.py`. `app/api/scenarios.py` switches to your loader as soon as `app.data.load` imports. Lane B deletes the stand-in after your A-01 merges.
- **Need:** `app.validate.validate_plan(scenario, result)`. Lane B passes the scenario with the result's edits already applied (`app.planning.edits.apply_edits`).
