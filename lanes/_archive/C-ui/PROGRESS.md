# Lane C · UI · progress

## Continue from here

- **Branch:** `lane/c-ui`. Based on Lane B `ce34f66`, which already includes `main` at `7a26d18`. This imports the actual OpenAPI and recordings without changing Lane B's files.
- **Setup:** Node 24, pnpm 11.25.0. `cd frontend && pnpm install --frozen-lockfile && pnpm dev`.
- **Check:** `make check-c`. Browser: `cd frontend && pnpm exec playwright install chromium && pnpm e2e`.
- **Read:** `frontend/README.md`, `lanes/C-ui/BRIEF.md`, `docs/DESIGN.md`.
- **Next:** run live against the integrated A+B backend after its rounding/baseline defects are fixed. Keep customer booking out of this scope.
- **Then:** add readiness/inventory edit controls and corresponding recordings. P2 animation and command palette are intentionally deferred.

## Done

2026-09-26: C-01 through C-16 and C-19 implemented. Evidence: `frontend/e2e/screenshots/`.

- React, Vite, TypeScript, Tailwind tokens, local Plex fonts, light/dark themes.
- Generated OpenAPI types, typed client, MSW recordings, unsupported-request errors.
- Calendar with capacity and locks, metrics, deferred jobs, linked SVG map and inspector.
- Crew-day disruption, stale hatch, revision protection, strict infeasibility and recovery.
- Immutable initial baseline, comparison, both recorded counterfactuals, JSON/CSV export.
- Source/assumption labels and explicit Not validated state. Invalid checked plans cannot be exported or displayed as assignments.
- Separate state/request hook and display components; hand-written TS/TSX files stay below 250 lines.

## Verification

- `make check-c`: passes typecheck, 13 unit tests, production build.
- Browser checks: complete demo flow, map linking, stale handling, recovery/comparison/counterfactuals, header/calendar/inspector, dark theme.
- Chromium CDN downloads were corrupt in the execution environment. Tests ran using a packaged Chromium binary through the optional executable-path setting. Normal team setup remains `playwright install chromium`.
- Screenshots inspected for layout and readability.

## In progress / limitations

- Mock data is unvalidated in the original recordings. Preserve the Not validated label; Lane C never changes that evidence.
- Only remove-crew-day disruption is exposed. No inventory/readiness controls yet.
- No P2 movement animation or command palette. No actual customer communication.
- Live mode is wired but not certified against the broken combined backend reviewed earlier.
