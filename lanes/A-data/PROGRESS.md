# Lane A · Data, Valuation, Truth · progress

## Continue from here
- Branch: `codex/lane-a-data` (Lane A implementation worktree).
- Setup: `cd backend && uv sync`.
- Check: `make check-a`.
- Read `AGENTS.md`, this lane brief, and `docs/CONTRACTS.md`.
- Next: A-10 deterministic standard fixture, then manifests and valuation.

## Done
- A-01: local scenario loader, structured errors, scenario list and summaries. Tiny hash matches the frozen fixture. Semantic input validation foundation included.
- A-02/A-03: all frozen hashes and round-trips pass; validator import boundaries enforced.
- A-04/A-05/A-06: independent constraints, states, usage and objective checks; every ViolationCode has a broken-plan test. No-incumbent responses validate shape only, not infeasibility proof.
- A-07: exhaustive oracle reproduces all five tiny plan cases and their unique optima/infeasibility.
- A-08/A-09: structured semantic checks, invalid raw values, valid ready-after-deadline cases, contradictory locks retained and reported.
- Evidence: `make check-a` passed, 57 tests.

## In progress
- Synthetic standard scenario and battery valuation.

## Blockers
- Publishing requires user approval after automatic review rejected exporting code to the unverified remote. Continue all local work.
- Tiny valuation is explicitly assumed zero, matching the frozen fixture; full price-backed valuation is next.
