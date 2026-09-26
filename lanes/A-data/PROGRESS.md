# Lane A · Data, Valuation, Truth · progress

## Continue from here
- Branch: `codex/lane-a-data` (Lane A implementation worktree).
- Setup: `cd backend && uv sync`.
- Check: `make check-a`.
- Read `AGENTS.md`, this lane brief, and `docs/CONTRACTS.md`.
- Next: A-02/A-03 contract hash checks, then replace the validator stub (A-04).

## Done
- A-01: local scenario loader, structured errors, scenario list and summaries. Tiny hash matches the frozen fixture. Semantic input validation foundation included.
- Evidence: `make check-a` passed, 11 tests.

## In progress
- Contract checks and independent validator.

## Blockers
- Publishing requires user approval after automatic review rejected exporting code to the unverified remote. Continue all local work.
- Validator is still explicitly unchecked until A-04 lands.
