# Lane R · Recovery engine · progress

## Continue from here

- Branch: `lane/R-engine`; isolated checkout `/Users/apr/Documents/ChatGPT/BPC Hackathon/BasePowerHackathon-R-engine`.
- Implementation complete for R-01 through R-14, including R-02b/c and R-03a/b. User explicitly requested one integration PR for these interconnected changes, overriding the per-item PR default. Human review and merge only.
- Setup: `cd backend && uv sync`; frontend tools use Node 24 and pnpm 11.25.
- Read: BRIEF.md, feature_list.json, docs/CONTRACTS.md (Lane R implementation notes), app/recovery/, and evidence.json.
- Check: `cd backend && uv run ruff check app/recovery app/baselines app/planning tests/lane_r && uv run pytest -q tests/lane_r tests/lane_b tests/contract`.
- Next: C integrates the live recovery response and H completes frontend hardening; requests are in their NEEDS.md files.

## Completed

- No-action repair retains original crews, reserves hard locks and unaffected bookings first, then repairs displaced visits while enforcing precedence, inventory, availability, and independent validation. Partial supplied current plans are preserved without implicit optimization.
- Reduced capacity, visit-specific appointment windows/customer rescheduling, cumulative capped overtime, pin and move edits; reject invalid references and out-of-horizon capacity. Independent validator unchanged.
- Live options, evaluation, and approval replace recovery stubs. Return no action, rebalance, overtime, and temporary capacity with impact cascades, operational counts, changed-visit explanations, per-crew loads, and explicit incremental economics.
- Bounded candidate search, current-plan solver hints, request caching, and independently checked feasible fallbacks when the solver times out. Feasible fallbacks are never presented as proven optimal.
- BLS May 2023 Houston electrician mean wage $28.33/person-hour, with source URL in the response. Crew size 2, overtime factor 1.5, temporary day $453.28, and max overtime 120 minutes are labeled assumptions. Penalties/customer-contact costs default off. Mixed 2018 energy/2023 wage dollars are explicitly illustrative.
- Lowest modeled cost compares every feasible returned option, including no action. Manual pin evaluation reports its modeled cost versus the unpinned alternative.
- Approval accepts unchanged server-issued options, rejects changed scenario inputs/revisions/tampering, revalidates, and returns bookings plus the effective scenario including added crew capacity.
- Additive contracts: EvaluateRequest.economics_overrides and ApproveResult.effective_scenario. Logged contract migration, regenerated schema, TypeScript types, and recorded responses.

## Verification and measured evidence

- Final lane check (recovery, planning, contracts): 176 passed, 1 skipped. Recovery, contract, and recorded-response integration selection: 66 passed.
- `make check-contracts`: 17 passed; `make check-a`: 124 passed; `make check-b`: 143 passed, 1 skipped. Ruff checks and required format checks passed.
- Frontend typecheck and production build passed. Frontend tests: 27 passed, 1 failed in the existing export test's stale `Not validated` expectation. H owns this test and the fix is recorded in its NEEDS.md; this PR must not be represented as entirely green or auto-merged.
- Independent evaluator returned PASS. Final regression recheck: 6 interactive/approval tests passed, including legacy final visits without explicit job_id.
- Opened and reviewed `evidence.json`: standard BA unavailable Thu June 7; interactive 2.433 seconds, broader search 11.356 seconds, repeated cached request 0.218 seconds, evaluate plus approve 2.731 seconds. Valuation was already prepared; these are local measurements, not latency guarantees.
- Both modes returned four independently validated feasible schedules. No action: 4 missed deadlines, $377.96 incremental modeled cost; overtime: 2 missed, $361.48; temporary crew: 0 missed, $453.28. The lowest-cost option and the fewest-missed-deadlines option differ intentionally.

## Scope limits and integration notes

- HTTP approval is stateless; it does not persist user sessions or support approval chaining. effective_scenario preserves resources/bookings for export and Python reuse. Do not reuse only new_current_plan against an unchanged roster after adding temporary capacity.
- Appointment windows remain in the option edit history and must be reapplied on subsequent analyses.
- Candidate search is bounded, not exhaustive. A solver's optimal status applies to that candidate's scheduling problem, not proof of the globally cheapest intervention. No autonomous recommendation or approval.
- Cold valuation is outside the interactive solver budget. Request cache and issued-option registry are in-process and bounded; restart/eviction requires re-evaluation.
- Weather replay remains parked and unchanged. UI components are left to C/H; generated API artifacts are included for the additive contract migration.

## PR #9 follow-up: skill-aware capacity candidates

- Fixed collaborator P1: inventory/readiness/appointment disruptions no longer select the first roster crew as the temporary template. Candidate capacity matches displaced visits' required skills and clusters, with dates bounded by readiness/appointments and relevant delayed receipt dates.
- Overtime and temporary capacity are returned only when independently valid and strictly better in operational ranking than both no action and rebalance. Equal outcomes, arbitrary option IDs, and price alone do not establish a recovery benefit. The response may therefore have fewer than three action options.
- Added regressions for standard B13 inventory delayed June 7 to June 8, no-disruption omission, and feasible-but-ineffective capacity omission. Updated the tiny fixture expectation to omit ineffective overtime.
- Recovery suite: 36 passed. Detailed inventory-delay output is in inventory-delay-evidence.json. Independent evaluator: PASS (8 recovery/interactive checks). Broader lane run: 178 passed, 1 skipped, with one obsolete all-three-option seam assertion; migrated that assertion to validate the new benefit rule and reran the affected seam/recorded checks: 33 passed. Ruff and format checks passed.
