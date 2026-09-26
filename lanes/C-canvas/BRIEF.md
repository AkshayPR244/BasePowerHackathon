# Lane C · Recovery Canvas

## Mission
Rollout Planner is a deterministic disruption-recovery planner for installation operations. It shows what broke, how the disruption cascades through the current plan, what feasible recovery actions exist, what each costs or saves relative to doing nothing, and lets the operations manager review, test changes, and approve. R is the product, W is the evidence, C is the experience.

Lane C builds the Recovery Canvas: one screen where the operations manager sees the disruption, follows the cascade through the plan, compares recovery actions against doing nothing, tests a change by hand, and approves. The plan lanes are the hero.

## Current state
- Done on `main` (PR #5): Vite + React + TS workspace with tokens, fonts, status system, MSW on recorded mocks, header, metrics, crew calendar, SVG map, deferred list, inspector, compare panel, export. It runs the tiny single-visit flow. Frontend e2e: 4 of 5 pass. `e2e/shell.spec.ts` and `src/lib/export.test.ts` fail on a stale "Not validated" expectation (plans are validated now).
- Frozen in this scaffold: recovery contracts in `frontend/src/api/generated.ts`, and recorded mocks for `/api/recovery/options`, `/evaluate`, `/approve`, `/api/storms`, `/api/cases`, `/api/season-replay` in `frontend/src/mocks/recorded/` (stub payloads carry `stub: true`).
- Two-visit data: `assignments` hold two entries per `site_id` for `standard`. Key visits by `job_id ?? site_id`. See `docs/CONTRACTS.md`, "Two visits per home".

## Owns
- `frontend/` except `frontend/src/views/season/` (Lane W), `frontend/src/api/generated.ts` (generated), and `frontend/src/mocks/recorded/` (recorded)
- `lanes/C-canvas/`

## Must not touch
- `frontend/src/views/season/` (Lane W's Storm Season view)
- `frontend/src/api/generated.ts` by hand (run `make types`)
- `frontend/src/mocks/recorded/` by hand (run `make mocks`)
- `backend/`, `data/`, `docs/`, `contracts/`

## Consumes
- `docs/DESIGN.md` (follow it exactly), `docs/CONTRACTS.md` (recovery shapes), `CLAUDE.md` ("Product (read first)" for vocabulary).
- Recorded mocks until the hour-4 sync, then the live API for one flow.
- `RecoveryOptionsResult` (impact, no_action, options), `RecoveryOption`, `ImpactAnalysis`, `ApproveResult`, `Case`.

## Provides
- The Recovery Canvas as the default view.
- A route or callback that opens a `Case` in the canvas, so Lane W's season view can link to it.
- Playwright specs and screenshots in `frontend/e2e/screenshots/`.

## Files to create (suggested)
| Path | Purpose |
|---|---|
| `src/views/Canvas.tsx` | Canvas layout: disruption bar, cascade strip, plan lanes, option cards, selected-option panel |
| `src/components/DisruptionBar.tsx` | One sentence plus visits affected, deadlines at risk, no-action cost |
| `src/components/CascadeStrip.tsx` | Clickable steps that highlight visits in the lanes |
| `src/components/PlanLanes.tsx` | Crews as rows, days as columns, install crews above the battery crew, arcs, hatched lost capacity, diff overlays |
| `src/components/OptionCard.tsx` | Action label, net impact, advantage vs no action, deadlines, customers to reschedule, overtime, "Lowest modeled cost" |
| `src/components/OptionPanel.tsx` | Plain-sentence changes, pinned headline numbers, Approve with a confirm summary |
| `src/state/recovery.ts` | Selected option, disruption, interventions, revision |
| `e2e/canvas.spec.ts` | Flow with screenshots |

## Scope

### P0
1. **Hygiene**: fix the stale "Not validated" expectations in `src/lib/export.test.ts` and `e2e/shell.spec.ts`. Plans are validated now.
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
Follow `docs/DESIGN.md`: warm paper, ink, one signal-orange accent, IBM Plex, status as shape + label + color, motion only to explain change, numbers right-aligned with tabular figures. Stub payloads (`stub: true`) show a visible "Stub data" label.

## Definition of done
- The canvas renders the recorded `recovery_options` mock for `standard` with battery crew BA out Thu 7 Jun: disruption bar, cascade, lanes with diff overlay, four option cards, the selected-option panel, and approve.
- After the hour-4 sync, one flow runs against the live API.
- Playwright: load → pick an option → inspect changes → approve, with screenshots.
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
