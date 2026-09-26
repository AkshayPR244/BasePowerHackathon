# Lane W · Weather evidence and trust · progress

> **PARKED (nice to have).** Revisit when R-engine and C-canvas P0 items pass. Nothing here blocks the demo.

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/W-evidence`. Then `git fetch origin && git merge origin/main`.
- **Setup:** `cd backend && uv sync`, and `cd frontend && pnpm install` for the season view.
- **Check:** `cd backend && uv run ruff check app/replay tests/lane_w && uv run pytest -q tests/lane_w tests/contract`
- **Read first:** `AGENTS.md`, `CLAUDE.md` ("Product (read first)", weather wording), `lanes/W-evidence/BRIEF.md`, `docs/CONTRACTS.md` (storm, case, season shapes), `backend/app/data/weather.py`, `backend/app/replay/service.py` (stub), `.claude/skills/data-provenance/SKILL.md`
- **Next:** W-01, the storm catalog with a manifest, then W-05 (500 error fix) and W-06 (late shipment scrub). Those two are small and unblock trust early.
- **Then:** the next item in `lanes/W-evidence/feature_list.json` with `"passes": false`, highest priority first.

## Done
- Scaffold (2026-09-26): storm, case, and season-replay contracts frozen. Stub `storms()`, `cases()`, `season_replay()` in `backend/app/replay/service.py`. Stub endpoints `/api/storms`, `/api/cases`, `/api/season-replay`. Recorded mocks.
- Already on `main`: weather rule and METAR parser (`app/data/weather.py`).

## In progress
- None.

## Blockers
- None.
