# Lane A · Data, Valuation, Truth · progress

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/a-data`. Then `git fetch origin && git merge origin/main`.
- **Setup:** `cd backend && uv sync`
- **Check:** `cd backend && uv run ruff check app/data app/valuation app/validate && uv run pytest -q tests/lane_a tests/contract` (becomes `make check-a` once it works)
- **Read first:** `AGENTS.md`, `lanes/A-data/BRIEF.md`, `backend/app/contracts/models.py`, `data/demo/tiny/`, `.claude/skills/data-provenance/SKILL.md`
- **Next:** A-01: load `data/demo/tiny` into contract models (`app.data.load_scenario`). Lane B waits on it, so open a PR as soon as it passes.
- **Then:** the next item in `lanes/A-data/feature_list.json` with `"passes": false`, highest priority first.

## Done
- Scaffold (2026-09-25): frozen contracts, empty lane packages, tiny fixture inputs and expected results. No loader, validator, or lane tests yet.

## In progress
- None.

## Blockers
- None.
