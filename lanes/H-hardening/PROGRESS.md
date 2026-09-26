# Lane H · UI hardening · progress

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/H-hardening`. Then `git fetch origin && git merge origin/main`.
- **Setup:** `cd backend && uv sync`, then `cd frontend && pnpm install`
- **Check:** `cd backend && uv run pytest -q tests/lane_h tests/contract && cd ../frontend && pnpm typecheck && pnpm test && pnpm build`
- **Read first:** `AGENTS.md`, `CLAUDE.md` ("Product (read first)"), `lanes/H-hardening/BRIEF.md`, `docs/CONTRACTS.md` (recovery shapes and stubs), `frontend/src/api/client.ts`, `backend/app/api/main.py` (exception handlers)
- **Next:** H-03 stub honesty and H-05 error and loading states, once C's layout pass (C-17 to C-19) lands. H-01, H-02, H-04 are done. H-07 (freeze) waits on R-23.
- **Then:** the next item in `lanes/H-hardening/feature_list.json` with `"passes": false`, highest priority first.

## Done
- 2026-09-26: H-04 (PR #11) stale Not validated tests. H-01 500 errors return a generic message with a request ID, details logged server-side. H-02 late-shipment example removed from README, DEMO, CONTRACTS, the recording script, and the recorded mocks (kept in the API and tests).
- Scaffold (2026-09-27): stub endpoints and recorded mocks exist and are schema-valid (`tests/contract/test_seams.py`).

## In progress
- None.

## Blockers
- None.
