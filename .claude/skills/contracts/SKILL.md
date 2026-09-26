---
name: contracts
description: How to read and use the frozen API contract (backend/app/contracts), regenerate OpenAPI and TypeScript types, and request a contract change. Use before adding a field, reading or writing a PlanResult, Scenario, Edit, or other shared model, touching contracts/openapi.json or frontend/src/api/generated.ts, or when a lane needs data another lane does not yet provide.
---

# Contracts

Full reference: `docs/CONTRACTS.md`. This skill is the short version.

## Source of truth

Pydantic models in `backend/app/contracts/` are the only definition of shared types.

| File | Holds |
|---|---|
| `models.py` | Every request, response, input, and data-product model |
| `enums.py` | `PlanStatus`, `StageStatus`, `Mode`, `Algorithm`, `ObjectivePolicy`, `ReasonCode`, `JobState`, `DataKind`, `ViolationCode`, `InputIssueCode`, `ChangeKind` |
| `units.py` | Annotated unit types and `SCHEDULING_TZ` |
| `hashing.py` | `scenario_hash(scenario, edits)` |

Generated from them (planned, see lane briefs):
- `contracts/openapi.json` via `scripts/export_openapi.py` (Lane B).
- `frontend/src/api/generated.ts` via `scripts/gen_types.sh` (Lane C).

Nobody hand-writes shared types. Nobody hand-edits generated files.

## Reading the models

- All models forbid extra fields and reject NaN or infinity.
- IDs are strings. Durations are integer minutes. Energy kWh, power kW, prices USD/MWh, value USD.
- Scheduling dates are `America/Chicago` calendar dates. Energy timestamps are UTC.
- `Edit` is a union discriminated by `kind`: `remove_crew_day`, `add_crew_day`, `delay_inventory`, `change_ready_date`, `force_include`.
- `PlanResult.validation.checked` is false until the independent validator ran. The UI shows "Not validated" then.
- `PlanResult.objective` is `None` when there is no plan (infeasible, timeout, invalid input).
- `revision` is a client counter. The server echoes it. The client drops responses with an old revision.
- `scenario_hash` = sha256 of scenario inputs plus edits. Use `app.contracts.hashing.scenario_hash`. Never compute it another way.

## Regenerating (planned commands)

```bash
make types     # contracts/openapi.json + frontend/src/api/generated.ts
make mocks     # frontend/src/mocks/recorded/*.json from the in-process API
```

Until the Makefile targets exist:

```bash
cd backend && PYTHONPATH=. uv run python ../scripts/export_openapi.py
./scripts/gen_types.sh
cd backend && PYTHONPATH=. uv run python ../scripts/record_mocks.py
```

Commit generated files in the same commit as the model change.

## Changing the contract

After the scaffold commit the contract is frozen.

Allowed without a human:
1. Add an optional field with a default to an existing model, or add a new model or enum member that no existing field requires.
2. Regenerate types and mocks in the same commit.
3. Log one line in `contracts/CHANGE_REQUESTS.md`: date, lane, model.field, reason.

Not allowed without a human (write a `PROPOSED` entry in `contracts/CHANGE_REQUESTS.md` and keep working around it):
- Rename or remove a field, model, or enum member.
- Change a type or unit.
- Add a required field.
- Change the meaning of an existing field.

If you need data another lane owns, write the request in `lanes/<their lane>/NEEDS.md`. Use a local synthetic stand-in, labeled, until it lands.

## Checks

- `backend/tests/contract/` round-trips every fixture and expected response through the models (Lane A creates it).
- `scripts/export_openapi.py --check` fails when `contracts/openapi.json` is stale.
- `make check-contracts` (planned) runs both and diffs `generated.ts`.
