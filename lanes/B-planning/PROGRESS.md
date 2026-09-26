# Lane B · Planning and API · progress

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/b-planning`. Then `git fetch origin && git merge origin/main`.
- **Setup:** `cd backend && uv sync`
- **Check:** `cd backend && uv run ruff check app/planning app/baselines app/compare app/api && uv run pytest -q tests/lane_b tests/contract` (becomes `make check-b` once it works)
- **Read first:** `AGENTS.md`, `lanes/B-planning/BRIEF.md`, `backend/app/contracts/models.py`, `data/demo/tiny/expected/`, `.claude/skills/ops-optimization/SKILL.md`
- **Next:** B-01: FastAPI app with every spec endpoint serving `data/demo/tiny/expected/*.json`, plus `scripts/export_openapi.py`. Lane C waits on `contracts/openapi.json`, so open a PR as soon as it passes.
- **Then:** the next item in `lanes/B-planning/feature_list.json` with `"passes": false`, highest priority first.

## Done
- Scaffold (2026-09-25): frozen contracts, an empty FastAPI app, expected tiny results. No routes, openapi.json, or lane tests yet.

## In progress
- None.

## Blockers
- None.
