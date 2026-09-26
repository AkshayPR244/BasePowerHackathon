# Lane R · Recovery engine · progress

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/R-engine`. Then `git fetch origin && git merge origin/main`.
- **Setup:** `cd backend && uv sync`
- **Check:** `cd backend && uv run ruff check app/recovery app/baselines app/planning tests/lane_r && uv run pytest -q tests/lane_r tests/lane_b tests/contract`
- **Read first:** `AGENTS.md`, `CLAUDE.md` ("Product (read first)"), `lanes/R-engine/BRIEF.md`, `docs/CONTRACTS.md` (recovery shapes), `backend/app/recovery/service.py` (stub), `backend/app/planning/solve.py`, `.claude/skills/ops-optimization/SKILL.md`
- **Next:** R-01, no action as a first-class `RecoveryOption` via the repair rule. Merge it early: C and H need it.
- **Then:** the next item in `lanes/R-engine/feature_list.json` with `"passes": false`, highest priority first.

## Done
- Scaffold (2026-09-26): recovery contracts frozen, stub `recover()`, `evaluate()`, `approve()` in `backend/app/recovery/service.py`, stub endpoints `/api/recovery/options`, `/evaluate`, `/approve`, recorded mocks.
- Already on `main`: two-visit `standard`, CP-SAT planner, validator, EDF and nearest-cluster baselines, `remove_crew_day`, `change_ready_date`, `add_crew_day`.

## In progress
- None.

## Blockers
- None.
