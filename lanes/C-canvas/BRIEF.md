# Lane C · Recovery Canvas

## Mission
Rollout Planner is a deterministic disruption-recovery planner for installation operations. It shows what broke, how the disruption cascades through the current plan, what feasible recovery actions exist, what each costs or saves relative to doing nothing, and lets the operations manager review, test changes, and approve. R is the product, C is the experience, H makes it demo-safe. Weather replay is a parked nice-to-have (`lanes/_parked/weather`).

Lane C builds the Recovery Canvas: one screen where the operations manager sees the disruption, follows the cascade through the plan, compares recovery actions against doing nothing, tests a change by hand, and approves. The plan lanes are the hero.

## Current state
- Done on `main` (PR #5): Vite + React + TS workspace with tokens, fonts, status system, MSW on recorded mocks, header, metrics, crew calendar, SVG map, deferred list, inspector, compare panel, export. It runs the tiny single-visit flow. Frontend e2e: 4 of 5 pass. `e2e/shell.spec.ts` and `src/lib/export.test.ts` fail on a stale "Not validated" expectation (plans are validated now).
- Frozen in this scaffold: recovery contracts in `frontend/src/api/generated.ts`, and recorded mocks for `/api/recovery/options`, `/evaluate`, `/approve` in `frontend/src/mocks/recorded/` (stub payloads carry `stub: true`). The storm, case, and season-replay mocks exist too, but weather is parked.
- Two-visit data: `assignments` hold two entries per `site_id` for `standard`. Key visits by `job_id ?? site_id`. See `docs/CONTRACTS.md`, "Two visits per home".

## Owns
- `frontend/` except the paths below
- `lanes/C-canvas/`

## Must not touch
- Lane H's paths: the rest of `frontend/e2e/` and test files, `frontend/src/api/client.ts`, `frontend/src/mocks/handlers.ts`, `frontend/playwright.config.ts`. Ask H through `lanes/H-hardening/NEEDS.md`.
- C does own its feature tests: `frontend/e2e/canvas*.spec.ts` and test files colocated with C's components, views, and state. C proves its own items with them.
- `frontend/src/api/generated.ts` by hand (run `make types`)
- `frontend/src/mocks/recorded/` by hand (run `make mocks`)
- `backend/`, `data/`, `docs/`, `contracts/`
- There is no season view in scope. Weather is parked.

## Consumes
- `docs/DESIGN.md` (follow it exactly), `docs/CONTRACTS.md` (recovery shapes), `CLAUDE.md` ("Product (read first)" for vocabulary).
- Recorded mocks until the hour-4 sync, then the live API for one flow.
- `RecoveryOptionsResult` (impact, no_action, options), `RecoveryOption`, `ImpactAnalysis`, `ApproveResult`.
- Lane H's `client.ts` (errors, `isStub`, revision guard) and its requests in `lanes/C-canvas/NEEDS.md`.

## Provides
- The Recovery Canvas as the default view.
- Stable `data-testid` hooks on the disruption bar, cascade steps, option cards, and Approve, so Lane H can write e2e specs.
- Screenshots for each item (H owns the spec files. C may ask H for a spec or add screenshots through H's specs).

## Files (as built)
| Path | Purpose |
|---|---|
| `src/views/Workspace.tsx` | Canvas layout: disruption bar, cascade strip, plan lanes, option cards, selected-option panel |
| `src/components/DisruptionBar.tsx` | One sentence plus visits affected, deadlines at risk, no-action cost |
| `src/components/CascadeStrip.tsx` | Clickable steps that highlight visits in the lanes |
| `src/components/CrewCalendar.tsx` | Crews as rows, days as columns, install crews above the battery crew, arcs, hatched lost capacity, diff overlays |
| `src/components/OptionCard.tsx` | Action label, net impact, advantage vs no action, deadlines, customers to reschedule, overtime, "Lowest modeled cost" |
| `src/components/OptionPanel.tsx` | Plain-sentence changes, pinned headline numbers, Approve with a confirm summary |
| `src/state/store.ts`, `src/state/usePlanner.ts` | Selected option, disruption, interventions, revision, and the API calls |

## Scope

### P0
1. **Two-visit rendering**: the current workspace renders `standard`, where `assignments` hold two entries per `site_id`. Key visits by `job_id ?? site_id`. The stale "Not validated" tests belong to Lane H (H-04).
2. **Disruption bar**: one sentence (`impact.headline`) plus visits affected, deadlines at risk, and the no-action cost.
3. **Cascade strip**: the steps from `impact.cascade` (disruption → direct → pushed → commitment). Clicking a step highlights its visits in the lanes.
4. **Plan lanes as the hero**: crews as rows, days as columns, install crews above the battery crew. Install → battery-day arcs. Hatched lost capacity. Diff overlays: moved visits ghost from the old cell and slide to the new one, unchanged visits fade.
5. **Option cards**: action label ("Crew IB +2h overtime"), net impact, advantage vs no action, deadlines, customers to reschedule, overtime. The `lowest_modeled_cost` option carries the tag "Lowest modeled cost". Never "Recommended". Never "Plan 3".
6. **Selected-option panel**: plain-sentence changes, pinned headline numbers, and Approve with a confirm summary (calls `/api/recovery/approve`).

### P1
7. Direct manipulation calling `/api/recovery/evaluate`: knock out a crew-day, drag a day's edge for overtime, drag a visit, pin a visit. Show a plain progress line ("Solving · 1.2 s"). Never a bare spinner.
8. Mini lane thumbnails on option cards.
9. Explanation drawer with the economic breakdown (`economics.lines`, each with its basis).
10. Assumptions panel with sources and tags. Editable economics (sends `economics_overrides`).

### P2
11. Map inset highlighting affected homes by cluster. No routes, no storm movement.
12. Keyboard shortcuts.
13. Dark mode polish.

## Design rules
Follow `docs/DESIGN.md`: warm paper, ink, one signal-orange accent, IBM Plex, status as shape + label + color, motion only to explain change, numbers right-aligned with tabular figures. Stub payloads (`stub: true`, exposed as `isStub` by H's `client.ts`) show a visible "Stub data" label.

## Definition of done
- The canvas renders the recorded `recovery_options_standard_storm` mock (the 14 Jun 2018 storm case on `standard`): disruption bar, cascade, lanes with diff overlay, four option cards, the selected-option panel, and approve.
- After the hour-4 sync, one flow runs against the live API.
- Playwright (spec owned by H): load → pick an option → inspect changes → approve, with screenshots.
- Lane check passes (below).

## Lane check
`cd frontend && pnpm typecheck && pnpm test && pnpm build`

## Cut list (cut in this order)
1. Map inset.
2. Mini lane thumbnails.
3. Drag a visit (keep pin and overtime).
Never cut the disruption bar, the plan lanes, the option cards, or approve.

## Working rules
- Branch `lane/C-canvas`. Pull `origin/main` at session start.
- Build on recorded mocks until the hour-4 sync. Do not wait for Lane R.
- One PR per feature item. Merge only after the checks and an evaluator PASS. Never push to `main`.
- Update `lanes/C-canvas/PROGRESS.md` after every item. Write requests to other lanes in `lanes/<their lane>/NEEDS.md`.
