# Lane H · UI hardening · progress

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/H-hardening`. Then `git fetch origin && git merge origin/main`.
- **Setup:** `cd backend && uv sync`, then `cd frontend && pnpm install`
- **Check:** `cd backend && uv run pytest -q tests/lane_h tests/contract && cd ../frontend && pnpm typecheck && pnpm test && pnpm build`
- **Read first:** `AGENTS.md`, `CLAUDE.md` ("Product (read first)"), `lanes/H-hardening/BRIEF.md`, `docs/CONTRACTS.md` (recovery shapes and stubs), `frontend/src/api/client.ts`, `backend/app/api/main.py` (exception handlers)
- **Next:** H-01, the 500 error fix, then H-02 the late-shipment scrub. Both are small. Then H-04, which fixes the two stale "Not validated" tests.
- **Then:** the next item in `lanes/H-hardening/feature_list.json` with `"passes": false`, highest priority first.

## Done
- Scaffold (2026-09-27): stub endpoints and recorded mocks exist and are schema-valid (`tests/contract/test_seams.py`).

## In progress
- None.

## Blockers
- None.
