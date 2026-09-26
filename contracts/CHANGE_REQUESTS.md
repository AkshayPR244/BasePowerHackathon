# Contract change requests

The contract in `backend/app/contracts/` is frozen as of the scaffold commit. Full protocol: `docs/CONTRACTS.md`.

- Additive (optional field with a default, new model, new enum member nothing requires): make the change, regenerate types and mocks in the same commit, add one line to the Log.
- Breaking (rename, remove, type or unit change, new required field, changed meaning): add a PROPOSED entry below. Keep working around it. A human decides.

## Log

| Date | Lane | Change | Reason |
|---|---|---|---|
| 2026-09-26 | B | Every error response (400, 404, 405, 422, 500) is an `ApiError`. OpenAPI documents `ApiError` for 400, 404, 422, 500 and no longer lists `HTTPValidationError`. `GET /api/health` adds `values` and `values_seconds`. | The UI handles one error shape. Health reports whether value tables are warm. |
| 2026-09-26 | A | `ScenarioConfig.parameters: list[Parameter] = []` and `ScenarioConfig.weather_rule: WeatherRule \| None = None`. New models `Parameter` (name, value, unit, kind, derivation, source) and `WeatherRule`. Both enter `scenario_hash` only when set, so existing hashes stay valid. | Show every operational number with its tag and source. Weather rule for the replay. |

## Proposed (waiting for a human)

| Date | Lane | Proposed change | Reason | Affects |
|---|---|---|---|---|
