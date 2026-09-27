# Scenario suite verification

Executed on 2026-09-26 from the `codex/scenario-suite` worktree.

## Results

- `cd backend && uv run pytest -q tests/scenario_suite`: 21 passed.
- `cd backend && uv run pytest -q tests/lane_a tests/lane_b tests/lane_r tests/contract tests/scenario_suite`: 305 passed, 1 skipped.
- `cd backend && uv run ruff check app/data tests/scenario_suite`: passed.
- `cd backend && uv run ruff format --check app/data tests/scenario_suite`: 15 files already formatted.
- `cd backend && uv run python ../scripts/export_openapi.py --check`: `openapi.json` is current.
- `cd frontend && pnpm typecheck`: passed.
- `cd frontend && pnpm test`: 30 passed in 5 files.
- `cd frontend && pnpm build`: passed; Vite reported its advisory warning for chunks over 500 kB.
- `cd frontend && pnpm exec prettier --check src e2e vite.config.ts`: passed.
- Independent evaluator review after the missing-narrative and stale-response fixes: PASS.

## Observed scenario behavior

All ten initial current plans are strict-feasible and independently validated with every home on time.

- `balanced_small`: 12 homes, 16.78% aggregate crew utilization, zero moves under healthy-baseline analysis.
- `tight_feasible`: removing the busiest battery day makes strict planning infeasible. No action misses 5 deadlines, overtime misses 3, and eligible temporary battery capacity misses 0. Battery utilization through the commitment deadline exceeds 85%.
- `crew_out_recoverable`: no action misses 4 deadlines; existing-crew rebalancing returns a validated on-time plan.
- `inventory_delay_recoverable`: the delayed receipt moves 6 battery visits; recovery remains on time.
- `readiness_appointment`: no action leaves one visit unscheduled; validated rebalancing honors the exact appointment window and restores all commitments.
- `skill_cluster_bottleneck`: the removed territory-specific battery day moves 6 visits. All emitted assignments retain the required battery skill and allowed cluster.
- `two_visit_cascade`: the appointment change moves the install and its dependent battery visit while preserving the two-business-day gap.
- `locked_infeasible`: removing an occupied locked crew-day leaves strict and recovery infeasible. No lock is silently moved.
- `late_overflow`: strict planning is infeasible after the receipt delay. Recovery completes all 12 homes late in overflow with none unscheduled.
- `value_sensitive`: under the same battery-day removal, both strict policy runs remain validated and on time; value-aware and deadline/travel-only schedules differ, and value-aware produces greater hindsight modeled operating margin.

The live preview at `http://127.0.0.1:5174` was inspected in the in-app browser. The selector listed all ten suite IDs; the bold, collapsible Scenario briefing displayed its operator story and persistent truth label; applying a primary disruption changed the briefing to its trigger/question and exposed the matching live recovery results.

## Reproducibility

The suite tests regenerate each scenario into a temporary directory and compare every operational input byte, generated manifest, primary-disruption preset, scenario hash, and solved current plan with the committed artifacts. Prepared Parquet files are compared byte-for-byte with the existing valid `standard` price/load inputs. Narrative prose is deliberately excluded from generation and is verified as frontend-only metadata.
