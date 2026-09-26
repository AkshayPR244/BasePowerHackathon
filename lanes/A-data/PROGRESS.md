# Lane A · Data, Valuation, Truth · progress

## Continue from here
- Branch: `lane/a-data` in the original checkout; implementation commits originated on `codex/lane-a-data`.
- Setup: `cd backend && uv sync --locked`.
- Check: `make check-a` from the repository root.
- Read `AGENTS.md` and `lanes/A-data/IMPLEMENTATION.md` for the interfaces, provenance and reproduction commands.
- All A-01 through A-18 items are implemented and their acceptance checks pass.
- Next: publish the branch and open a PR once the user authorizes the remote write. Lane B can import the local implementation now. Do not merge to main.

## Done
- A-01: loader, scenario list and summaries; structured errors and exact frozen tiny hash.
- A-02/A-03: scenario/result round trips, all expected hashes, and absolute/relative import boundary checks.
- A-04/A-05/A-06: independent hard-constraint, state, crew-usage and objective validation; every ViolationCode tested with a broken plan.
- A-07: exhaustive oracle reproduces all five frozen plan cases and unique optima/infeasibility.
- A-08/A-09: duplicate/reference/value/date checks; ready-after-deadline allowed; contradictory locks retained and reported.
- A-10/A-11: deterministic 30-job standard fixture, SHA-256 manifests and provenance checks.
- A-12: actual ERCOT 2018 archive prepared; 5,376 observed Houston quarter-hours; explicit LZ filter, DST conversion, no gap filling.
- A-13/A-14: HiGHS battery MILP, binary charge/discharge exclusivity, energy conservation and reserve boundaries.
- A-15/A-16: 360 site/date values, identical-site solve reuse, content-hashed atomic cache with invalidation tests.
- A-17: 30 bounded HCAD parcel candidates successfully prepared and loaded. Observed files remain local/ignored; no owner or address fields in prepared data.
- A-18: actual ResStock AMY2018 Texas archetype prepared and aligned to prices, modeled provenance, standalone load-limited sensitivity verified. Default API valuation remains unrestricted export.
- Evidence: `make check-a` passes 101 tests. Standard existing plan independently validates with 30 on-time assignments. See `evidence.json` for measured valuation/cache results.

## In progress
- None.

## Blockers and limits
- Automatic approval review rejected pushing code to the unverified remote. No push or PR was made. User approval is required to publish to `https://github.com/AkshayPR244/BasePowerHackathon.git`.
- HCAD source redistribution terms remain unverified; regenerate the ignored local sample with the documented explicit command.
- No-incumbent validation checks response shape, not a solver's infeasibility proof. The exhaustive oracle supplies the tiny-case proof.
- Frozen contracts, expected tiny results, Lane B source and frontend source were not changed.
