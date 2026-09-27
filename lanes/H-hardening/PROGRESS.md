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
- 2026-09-26: QA sweep fixes (branch `fix/tooling`). `make check` runs the whole backend (`check-backend`), plus new `check-r` and `check-h`. Kill switch and STEER reach worktree agents. Checkpoint commits skip main and e2e screenshots. API: request size and revision bounds, honest 422 versus 500 for recovery errors, no paths or exception text in load errors or `/api/health`, scenario cache off the event loop, CORS for :4173 with exposed headers. `docs/CONTRACTS.md` and `docs/DEMO.md` match the current product. H-10 still needs `docs/FIRST_PRINCIPLES.md` and README known limitations.
- 2026-09-26: H-04 (PR #11) stale Not validated tests. H-01 500 errors return a generic message with a request ID, details logged server-side. H-02 late-shipment example removed from README, DEMO, CONTRACTS, the recording script, and the recorded mocks (kept in the API and tests).
- Scaffold (2026-09-27): stub endpoints and recorded mocks exist and are schema-valid (`tests/contract/test_seams.py`).

## In progress
- None.

## Blockers
- None.
