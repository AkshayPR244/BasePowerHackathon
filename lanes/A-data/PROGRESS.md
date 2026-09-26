# Lane A · Data, Valuation, Truth · progress

## Continue from here
- Branch: `codex/lane-a-data` (Lane A implementation worktree).
- Setup: `cd backend && uv sync`.
- Check: `make check-a`.
- Read `AGENTS.md`, this lane brief, and `docs/CONTRACTS.md`.
- Next: A-18 ResStock load-limited sensitivity, then final integration review.

## Done
- A-01: local scenario loader, structured errors, scenario list and summaries. Tiny hash matches the frozen fixture. Semantic input validation foundation included.
- A-02/A-03: all frozen hashes and round-trips pass; validator import boundaries enforced.
- A-04/A-05/A-06: independent constraints, states, usage and objective checks; every ViolationCode has a broken-plan test. No-incumbent responses validate shape only, not infeasibility proof.
- A-07: exhaustive oracle reproduces all five tiny plan cases and their unique optima/infeasibility.
- A-08/A-09: structured semantic checks, invalid raw values, valid ready-after-deadline cases, contradictory locks retained and reported.
- A-10/A-11: deterministic 30-job synthetic standard scenario and SHA-256 manifests.
- A-12: actual ERCOT 2018 archive ingested, LZ type selected explicitly; 5,376 Houston quarter-hours for June 4–July 29. DST/gap/duplicate tests pass.
- A-13/A-14: continuous-horizon HiGHS MILP, binary charge mode, equal reserve boundaries; physics and negative-price tests pass.
- A-15/A-16: 360 standard site/date values, input-hashed atomic cache, identical-site solve reuse. Measured first preparation 21.221 seconds; cache reload 0.001 seconds.
- A-17: bounded HCAD queries verified with 30 real parcel candidates; only geometry and hashed IDs survive preparation. Observed scenario files stay local/ignored pending redistribution terms. Recipes and manifests are tracked.
- Evidence: `make check-a` passed, 90 tests.

## In progress
- ResStock load preparation and final review.

## Blockers
- Publishing requires user approval after automatic review rejected exporting code to the unverified remote. Continue all local work.
- Tiny valuation remains explicitly assumed zero, matching the frozen fixture. Standard uses observed prices and modeled operating margin.
