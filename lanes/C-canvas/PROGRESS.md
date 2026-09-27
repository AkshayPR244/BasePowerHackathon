# Lane C · Recovery Canvas · progress

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/C-canvas`. The live recovery canvas (C-16) merged with main in `integrate/ui-canvas`.
- **Setup:** `cd frontend && pnpm install`
- **Check:** `cd frontend && pnpm typecheck && pnpm test && pnpm build && pnpm exec playwright test` (mock mode). Set `PW_PORT` to run Playwright on a port other than 5173. Live checks: `CANVAS_LIVE=1` with a live-mode dev server and the API on port 8000.
- **Read first:** `AGENTS.md`, `CLAUDE.md` ("Product (read first)"), `lanes/C-canvas/BRIEF.md`, `docs/DESIGN.md`, `frontend/src/views/LiveRecoveryCanvas.tsx`, `frontend/src/views/Canvas.tsx`, `frontend/src/lib/recovery.ts`
- **Routes:** `/` opens the live recovery canvas. `/?view=workspace` and `/?scenario=<id>` open the day 1 workspace with the storm case, the scenario suite, and "Advanced: baseline plan".
- **Next:** decide if the live canvas needs the economics assumptions panel and the scenario picker. Until then they stay in the workspace view.
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
- C-16: rebuilt the default view as a trigger-driven live recovery canvas with crew/home figures, a validated option frontier, and approval. It has no weather framing. All six trigger definitions and the synthetic N/S/W cluster key are visible. During a solve, the prior revision stays visible under a stale label with approval paused; one API-derived move path compares the previous displayed plan with the new recovery, while a stronger persistent tint marks cumulative moves from the current plan. The home timeline uses the same previous-plan baseline. Figure 2 no longer repeats option names around points; each point remains accessible and each option name is shown in its selectable chip. Browser coverage checks crew role against each visible visit type across every selectable option. The independent validator enforces the same skill rule, and its battery-crew/install mismatch test passes. Disruptions and home protection call `/api/recovery/evaluate`; returned custom plans are shown only when validated at the current revision, and stale evaluator responses are ignored. All eight C-owned live Playwright flows pass at 1440×900 with screenshots after each interaction and no page scroll. Frontend unit tests (29), typecheck, build, and format check pass.

- QA sweep fixes (2026-09-26, `fix/canvas`): the app opens on `standard` and the Recovery Canvas is the page. The day 1 workspace is behind "Advanced: baseline plan" and opens by default only for scenarios with no recovery case (`?scenario=tiny`). Canvas state is keyed on scenario and demo session. Approval resets on option change and ignores stale responses. The confirm dialog is a modal `<dialog>` that freezes its option. Ghosts render in lost crew-day cells. Invalid, timed-out, and unproven options are labeled, never drawn, and cannot be approved. Economics overrides keep the last good options on error and offer Reset assumptions. Evaluate sends overrides and the analysis revision. Mocks match on the full recovery request. Theme follows the system and persists. Light tokens pass AA (`--accent #c4470a`, `--st-late #8a6508`).
- C-17 to C-21 pass in mock mode. Evidence: `frontend/e2e/screenshots/canvas-first.png`, `canvas-dark.png`.

- Integration with main (`integrate/ui-canvas`): the live canvas is the default page. It ignores stale approvals, uses a modal confirm dialog, draws ghosts in lost crew-day cells, labels withheld and unproven options, follows the system theme, and keeps locked rows locked. Mock tests and screenshots: `frontend/e2e/canvas-live.spec.ts`, `frontend/e2e/screenshots/live-canvas.png`, `live-canvas-knockout.png`, `live-canvas-dark.png`.

## In progress
- None.

## Blockers
- The live checks for C-08, C-09, and C-12 were not run in this pass. The backend was changing. Needs: a running live API on port 8000.
- `docs/DESIGN.md` still lists the old palette. The light tokens are now `--accent #b03f33`, `--st-scheduled #456b60`, `--st-locked #526c7d`. Docs are not in lane C's paths.
- Knock out on a crew-day with locked installs (Mon 4 Jun) makes every option infeasible. The canvas shows the reason. Decide if the canvas should block that click.
- The H-owned e2e specs still test the workspace view at `/?scenario=tiny`. The live canvas has its own mock and live tests in `frontend/e2e/canvas.spec.ts`.
