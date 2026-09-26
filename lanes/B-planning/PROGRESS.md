# Lane B · Planning and API · progress

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/b-planning`. Then `git fetch origin && git merge origin/main`. Open PR: #2.
- **Setup:** `cd backend && uv sync`
- **Check:** `cd backend && uv run ruff check app/planning app/baselines app/compare app/api tests/lane_b && uv run pytest -q tests/lane_b tests/contract` (becomes `make check-b` once it works)
- **Read first:** `AGENTS.md`, `lanes/B-planning/BRIEF.md`, `backend/app/planning/solve.py`, `.claude/skills/ops-optimization/SKILL.md`
- **Next:** B-16 once Lane A ships `data/demo/standard`. Replace the skipped `test_standard` in `tests/lane_b/test_api.py`, then add the standard scenario to `scripts/record_mocks.py`.
- **Then:** delete `backend/app/api/fixture_loader.py` once `app.data.load` merges. `app/api/scenarios.py` already prefers it.

## Done
- Scaffold (2026-09-25): frozen contracts, an empty FastAPI app, expected tiny results.
- 2026-09-26: B-01 to B-15 and B-17 to B-19. 88 tests pass, 2 skipped (standard fixture, opt-in 100-job timing).
  - CP-SAT planner in `app/planning/`. Strict and recovery modes. Five lexicographic recovery stages under one time budget.
  - Matches every tiny expected result exactly: strict, strict infeasible, recovery, diff, and both counterfactuals.
  - Blocked jobs carry reason codes. Lock conflicts are reported, never dropped.
  - Strict infeasibility from capacity or inventory names the jobs that conflict. It uses assumption literals in a single-worker solve (`app/planning/infeasibility.py`).
  - EDF and nearest-cluster-first baselines use the same rules and the same validator call.
  - Stateless compare and counterfactual endpoints.
  - Value-aware objective reads `app.valuation.value_table.value_table(scenario)` when Lane A ships it. Only rows with `solver_status == "optimal"` count. The result labels unresolved rows.
  - `contracts/openapi.json` and `frontend/src/mocks/recorded/` come from the real planner.

## Measurements (this laptop, synthetic test scenarios from `tests/lane_b/conftest.py`)
- 30 jobs, 3 crews, 10 days: the four priority stages prove optimal in under 0.2 s. The travel stage proves optimal in 0.2 to 0.7 s on 3 of 4 seeds. Seed 3 needs 17.5 s to prove travel. With a 4.5 s limit it returns `feasible` with the travel gap reported.
- 100 jobs, 6 crews, 10 days, 20 s budget: priority stages prove optimal in about 1 s. Travel ends `feasible` with a 2 to 9% gap.
- A redundant per-cluster capacity cut took seed 3 from "no proof in 20 s" to "proof in 17.5 s".

## In progress
- None.

## Blockers
- B-16 needs `data/demo/standard` from Lane A. Request is in `lanes/A-data/NEEDS.md`.
- `validate_plan` is still Lane A's stub. Every result shows `validation.checked: false` until it lands. The planner already raises `InvalidPlanError` (HTTP 500) if the real validator rejects a plan.
