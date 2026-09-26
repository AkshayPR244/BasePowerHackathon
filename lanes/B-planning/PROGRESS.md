# Lane B · Planning and API · progress

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/b-planning`. Then `git fetch origin && git merge origin/main`. Open PR: #2. It already contains `lane/a-data` (PR #3), so merge #3 first.
- **Setup:** `cd backend && uv sync`
- **Check:** `cd backend && uv run ruff check app/planning app/baselines app/compare app/api tests/lane_b && uv run pytest -q tests` (becomes `make check-b` once it works)
- **Read first:** `AGENTS.md`, `lanes/B-planning/BRIEF.md`, `backend/app/planning/solve.py`, `.claude/skills/ops-optimization/SKILL.md`
- **Next:** no feature-list items remain. Useful follow-ups, in order:
  1. Pre-warm the standard value cache at API startup, or document `make demo` doing it. A cold cache costs about 21 s once.
  2. Build a disruption on standard where energy value changes the recovery. On standard, EDF ties the optimizer on value and travel.
  3. Speed up the travel stage (symmetry breaking between identical crews).

## Done
- Scaffold (2026-09-25): frozen contracts, an empty FastAPI app, expected tiny results.
- 2026-09-26: all 19 feature items pass. 189 tests pass, 1 skipped (opt-in 100-job timing).
  - CP-SAT planner in `app/planning/`. Strict and recovery modes. Five lexicographic recovery stages under one time budget.
  - Matches every tiny expected result exactly: strict, strict infeasible, recovery, diff, and both counterfactuals.
  - Uses Lane A's loader, validator, and value table. Every plan passes `validate_plan`. A rejected plan raises `InvalidPlanError` (HTTP 500), never a result.
  - Blocked jobs carry reason codes. Lock conflicts are reported, never dropped.
  - Strict infeasibility from capacity or inventory names the jobs that conflict (assumption literals, single-worker solve).
  - EDF and nearest-cluster-first baselines report in recovery terms because a greedy rule may miss deadlines.
  - Counterfactual summaries name displaced jobs: "N-04 is back on time. S-04 becomes late instead."
  - Recorded mocks cover tiny and standard, including the standard late-shipment disruption.
  - Fixed Lane A's value cache key (commit 30c0290 on `lane/a-data`). A crew or plan edit no longer re-values.

## Measurements (this laptop)
- Standard, 30 jobs: strict 0.4 s. Recovery after a disruption 0.45 to 1.3 s. All validated. The first run on a cold value cache adds about 21 s of valuation.
- Standard late shipment (Thursday's 9 units of B13 arrive Monday): 3 jobs late, 16 move, value down $19.13.
- Standard: EDF matches the optimizer on value ($1998.39) and travel (1190 min). Energy-aware scheduling did not beat the baseline here. Say so in the demo.
- Synthetic 30 jobs: priority stages prove optimal in under 0.2 s. The travel stage can need up to 17.5 s to prove. With a 4.5 s limit it returns `feasible` with the gap reported.
- Synthetic 100 jobs, 20 s budget: priority stages prove optimal in about 1 s. Travel ends `feasible` with a 2 to 9% gap.

## In progress
- None.

## Blockers
- None.
