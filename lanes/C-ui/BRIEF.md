# Lane C · UI

## Mission
Rollout Planner is a planning and recovery analysis tool for residential battery installers. It takes an installation plan plus a disruption (crew out, late shipment, slipped approval), finds the best recovery, and explains what is at risk and why.

Lane C builds one dense, calm operator workspace that shows the plan, the disruption, the recovery, what is at risk, and why. It should look like a tool a sharp infrastructure team uses daily.

## Current state
- Delivered: `frontend/` directory skeleton only. No Vite app, no packages, no types, no mocks.
- Expected responses exist in `data/demo/tiny/expected/*.json` (PlanResult, PlanDiff, CounterfactualResult shapes).
- Lane B produces `contracts/openapi.json` (B-01) and `frontend/src/mocks/recorded/` (B-02). Do not wait for them. Start with the app and tokens.

## Owns
- `frontend/` except `frontend/src/api/generated.ts` and `frontend/src/mocks/recorded/`
- `scripts/gen_types.sh`
- `lanes/C-ui/`

## Must not touch
- `frontend/src/api/generated.ts` by hand (generated from `contracts/openapi.json`)
- `frontend/src/mocks/recorded/` (Lane B's `scripts/record_mocks.py` writes it)
- `backend/`, `data/`, `contracts/`

## Inputs
- `docs/DESIGN.md` (follow it exactly), `docs/SPEC.md` sections 3 and 10, `docs/CONTRACTS.md`.
- `contracts/openapi.json` once B-01 lands.
- `frontend/src/mocks/recorded/index.json` once B-02 lands.

## Outputs
- The workspace in `frontend/src/`, running on MSW mocks by default and on the live API with `VITE_API_MODE=live`.
- Playwright e2e plus screenshots in `frontend/e2e/screenshots/`.

## Stack
pnpm, React + TypeScript + Vite, Tailwind v4 driven by CSS variable tokens, TanStack Query, Zustand, MSW, Vitest, Playwright, `openapi-typescript` + `openapi-fetch`, `@fontsource/ibm-plex-sans` and `@fontsource/ibm-plex-mono`. No map library.

## Required pnpm scripts
`dev`, `build`, `typecheck` (`tsc --noEmit`), `test` (`vitest run`), `e2e` (`playwright test`). The planned Makefile targets call these.

## Files (create)
| Path | Purpose |
|---|---|
| `package.json`, `vite.config.ts`, `tsconfig.json`, `index.html` | Vite app. Proxy `/api` to `http://localhost:8000` in live mode |
| `public/mockServiceWorker.js` | From `pnpm exec msw init public` |
| `scripts/gen_types.sh` (repo root) | `openapi-typescript ../contracts/openapi.json -o src/api/generated.ts` |
| `src/design/tokens.css` | Color, type, spacing tokens. Light and dark |
| `src/design/status.tsx` | Status glyph + label + color for every `JobState` |
| `src/api/client.ts` | `openapi-fetch` client over `generated.ts` |
| `src/mocks/handlers.ts` | MSW handlers over `recorded/index.json`. Match `POST /api/plans` on `scenario_id` + `mode` + `edits`. Echo the request `revision`. Unmatched: 501 `ApiError` |
| `src/mocks/browser.ts` | Start MSW when `VITE_API_MODE` is not `live` |
| `src/state/store.ts` | Zustand: scenario, edits, revision, selection, baseline |
| `src/views/Workspace.tsx` | Layout of all panels |
| `src/components/Header.tsx` | Scenario, provenance badge, dates, policy, solve status |
| `src/components/MetricsStrip.tsx` | On-time, late, unscheduled, value, utilization, moved installs |
| `src/components/CrewCalendar.tsx` | One row per crew, capacity bars, lock marks |
| `src/components/DeferredList.tsx` | Unscheduled and blocked jobs with reasons |
| `src/components/Inspector.tsx` | Readiness, requirements, reason, counterfactual actions |
| `src/components/SiteMap.tsx` | SVG map from `Site.lon/lat` and `Cluster.outline` (P1) |
| `src/components/ComparePanel.tsx` | Changelog-style diff (P1) |
| `src/components/EditControls.tsx` | Disruptions: remove crew-day, delay inventory, change ready date (P1) |
| `src/lib/export.ts` | JSON + CSV download (P1) |
| `playwright.config.ts`, `e2e/*.spec.ts` | Flows with screenshots |

## Before recorded mocks exist
Point MSW at `data/demo/tiny/expected/*.json` (Vite can import them with `server.fs.allow`). For `GET /api/scenarios/tiny`, hand-transcribe `data/demo/tiny/*.csv` into `src/mocks/fixtures/scenario_tiny.json`, label it "hand-transcribed, replace with recorded" in PROGRESS.md, and delete it once B-02 lands.

## Scope

### P0 (vertical slice first)
1. Vite app with the required scripts, Tailwind v4, self-hosted Plex fonts, `tokens.css` per `docs/DESIGN.md`. `pnpm build` passes.
2. Types: `scripts/gen_types.sh` generates `src/api/generated.ts` from `contracts/openapi.json`. Typed `client.ts`.
3. MSW wiring: handlers over recorded mocks (or the expected JSON until B-02 lands). Default mode is mock.
4. App shell renders the tiny strict plan: header, metrics strip, crew calendar, deferred list, inspector.
5. Status system: shape + label + color. Never color alone.
6. Show `validation.checked`. If false, show "Not validated" next to the solve status.
7. Header badge shows `synthetic` and provenance.

### P1
8. Disruption controls. A disruption (an edit) bumps `revision` and marks the result stale: diagonal hatch plus a "previous result" label. Discard any response whose `revision` is not current.
9. Solve and re-solve. When strict is infeasible, show its message and offer recovery.
10. Compare panel: baseline versus current, changelog-style, via `POST /api/plans/compare`. The baseline is immutable until replaced.
11. Map: plain SVG, no tiles, no map library. Selection linked with the calendar.
12. Inspector counterfactual actions via `POST /api/plans/counterfactual`.
13. Export JSON + CSV of assignments, missed commitments, assumptions, and solver status.

### P2
14. Animated re-plan: jobs move from the old cell to the new cell with a brief highlight. Respect `prefers-reduced-motion`.
15. Keyboard shortcuts: R re-solve, C compare, / search. Command bar.
16. Dark mode from the same tokens.

## Definition of done
- Renders every recorded mock fixture.
- Playwright e2e passes: load, remove a crew-day, solve, compare, export.
- Screenshots saved to `frontend/e2e/screenshots/` as evidence.
- `make check-c` passes (planned target. Until it exists: `cd frontend && pnpm typecheck && pnpm test && pnpm build`).

## Cut list (cut in this order)
1. Command bar.
2. Animated re-plan (keep the moved-job highlight).
3. Dark mode.
4. Map (keep the cluster column in the calendar).
Never cut the stale state, revision checks, or the "Not validated" label.

## Working rules
- Build against MSW mocks. Do not wait for the backend.
- If you need a response that is not recorded, write it to `lanes/B-planning/NEEDS.md`. Do not hand-write files in `recorded/`.
- Pull `origin/main` at session start. Open a small PR to main with `gh pr create` when your check passes and a P0 item lands. Do not merge it yourself.
- Update `lanes/C-ui/PROGRESS.md` after every feature.
