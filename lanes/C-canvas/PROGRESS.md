# Lane C · Recovery Canvas · progress

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/C-canvas`, synced through `origin/main` at the Lane R integration. Push the completed C changes and request review.
- **Setup:** `cd frontend && pnpm install`
- **Check:** `cd frontend && pnpm typecheck && pnpm test && pnpm build`
- **Read first:** `AGENTS.md`, `CLAUDE.md` ("Product (read first)"), `lanes/C-canvas/BRIEF.md`, `docs/DESIGN.md`, `docs/CONTRACTS.md` (recovery shapes), `frontend/src/mocks/recorded/index.json`, `.claude/skills/design-system/SKILL.md`
- **Next:** No unchecked C feature items remain. Commit and push the C work, then request team/evaluator review.
- **Then:** the next item in `lanes/C-canvas/feature_list.json` with `"passes": false`, highest priority first.

## Done
- Scaffold (2026-09-26): recovery mocks recorded (storm, case, and season-replay mocks too, but weather is parked). `generated.ts` regenerated with the recovery contracts.
- Already on `main` (PR #5): the tiny workspace.
- C-01: the standard workspace renders distinct install and battery-day visits. Acceptance evidence: `frontend/e2e/screenshots/standard-two-visit.png`. Focused Playwright, typecheck, build, and the 26 unit tests outside the known H-owned stale export test pass.
- C-02: standard displays the recovery headline, affected visits, deadlines at risk, and no-action modeled cost. The bar describes the disruption as a modeled replay. Acceptance evidence: `frontend/e2e/screenshots/canvas-disruption.png`.
- C-03: cascade steps render from impact data and selecting a step highlights matching visits. Focused Playwright acceptance passes.
- C-04: install crews appear before battery crews. The calendar draws install-to-battery SVG connectors and hatches the storm-lost crew-days. Acceptance screenshot: `frontend/e2e/screenshots/canvas-lanes.png`.
- C-05: selected recovery differences show previous crew-day ghosts, moved visits, and faded unchanged visits. Reduced-motion browser coverage passes. Evidence: `frontend/e2e/screenshots/canvas-diff.png`.
- C-06: four recovery option cards show action, modeled costs, deadlines, customers to reschedule, overtime, and the lowest-modeled-cost tag. Evidence: `frontend/e2e/screenshots/canvas-options.png`.
- C-07: selected option review and confirmation call the approve endpoint. The integrated service validates the issued option before approval. Evidence: `frontend/e2e/screenshots/canvas-approve.png`.
- C-08: crew knockout, overtime, pin, and move controls call `/api/recovery/evaluate`; all four requests pass against the integrated live service.
- C-09: the standard recovery canvas and approval flow run against the integrated live API. Evidence: `frontend/e2e/screenshots/canvas-live.png`.
- C-10: option cards show before/after crew-load mini lanes. Evidence: `frontend/e2e/screenshots/canvas-thumbnails.png`.
- C-11: the selected option's cost drawer lists every economic line and basis. Evidence: `frontend/e2e/screenshots/canvas-drawer.png`.
- C-12: editable economic assumptions show source/kind/unit and send changes in `economics_overrides`; verified against the integrated live service.
- C-13: affected homes are highlighted and counted by cluster, with no routes or storm movement.
- C-14: number keys select options, A opens approval, and K tests a crew-day knockout.
- C-15: the canvas remains visible in dark mode. Evidence: `frontend/e2e/screenshots/canvas-dark.png`.

## In progress
- None.

## Blockers
- `pnpm test` still fails only at the known H-04 stale expectation in `src/lib/export.test.ts`. C left that H-owned test unchanged; 27 of 28 frontend unit tests pass.
