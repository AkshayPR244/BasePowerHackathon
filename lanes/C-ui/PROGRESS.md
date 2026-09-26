# Lane C · UI · progress

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/c-ui`. Then `git fetch origin && git merge origin/main`.
- **Setup:** `cd frontend && pnpm install   # after C-01 creates package.json`
- **Check:** `cd frontend && pnpm typecheck && pnpm test && pnpm build` (becomes `make check-c` once it works)
- **Read first:** `AGENTS.md`, `lanes/C-ui/BRIEF.md`, `docs/DESIGN.md`, `backend/app/contracts/models.py`, `data/demo/tiny/expected/`, `.claude/skills/design-system/SKILL.md`
- **Next:** C-01: create the Vite + React + TS app with tokens and fonts per `docs/DESIGN.md`. Build against mocks. Do not wait for the backend.
- **Then:** the next item in `lanes/C-ui/feature_list.json` with `"passes": false`, highest priority first.

## Done
- Scaffold (2026-09-25): empty `frontend/` directories and `docs/DESIGN.md`. No app yet.

## In progress
- None.

## Blockers
- None.
