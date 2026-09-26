# Lane H · UI hardening

## Mission
Rollout Planner is a deterministic disruption-recovery planner for installation operations. It shows what broke, how the disruption cascades through the current plan, what feasible recovery actions exist, what each costs or saves relative to doing nothing, and lets the operations manager review, test changes, and approve. R is the product, C is the experience, H makes it demo-safe. Weather replay is a parked nice-to-have (`lanes/_parked/weather`).

Lane H makes the recovery flow demo-safe and trustworthy end to end: live API wiring, error and loading states, stub and validation honesty, tests, accessibility, performance at demo resolution, and the freeze and record tooling. H does not build new canvas features (that is C) or engine logic (that is R). When H needs a change in one of C's components, H writes it to `lanes/C-canvas/NEEDS.md`.

## Current state
- Done on `main`: the day 1 workspace (PR #5), recorded mocks, and MSW in recorded and live modes. Frontend e2e: 4 of 5 pass. `e2e/shell.spec.ts` and `src/lib/export.test.ts` fail on a stale "Not validated" expectation (plans are validated now).
- Frozen in this scaffold: the recovery contracts and stub endpoints. Stub payloads carry `stub: true`, and the endpoints send `X-Rollout-Stub: true`. `tests/contract/test_seams.py` covers them.
- Known defects H owns:
  - The 500 handler returns exception text to the client (`backend/app/api/main.py`, `_unexpected`).
  - The late-shipment example is still in `README.md`, `docs/DEMO.md`, `docs/CONTRACTS.md`, `scripts/record_mocks.py`, and the recorded mocks.

## Owns
- `frontend/e2e/` except C's `canvas*.spec.ts`, and `frontend/playwright.config.ts`
- Frontend test infrastructure and test files outside C's components, views, and state (C writes the tests for its own features)
- `frontend/src/api/client.ts` (ApiError parsing, stub detection from the `stub` field and the `X-Rollout-Stub` header, the revision guard)
- `frontend/src/mocks/handlers.ts`
- Exception handlers in `backend/app/api/main.py` (only those)
- `backend/tests/lane_h/`
- `scripts/record_mocks.py`, `scripts/build_stubs.py`, `scripts/freeze.sh` (new), a `make freeze` target in the `Makefile`
- `README.md`, `docs/DEMO.md`, `docs/FIRST_PRINCIPLES.md` (new), `docs/STATUS_START.md`
- `lanes/H-hardening/`

## Must not touch
- `backend/app/contracts/` except additive, logged changes (see `docs/CONTRACTS.md`)
- `backend/app/recovery/`, `backend/app/planning/`, `backend/app/baselines/` (Lane R)
- Frontend components, views, state, and design (`frontend/src/components/`, `views/`, `state/`, `design/`): Lane C. Ask through `lanes/C-canvas/NEEDS.md`.
- `frontend/src/api/generated.ts` and `frontend/src/mocks/recorded/` by hand (run `make types` and `make mocks`)
- `lanes/_parked/weather` and `backend/app/replay/` (parked)

## Consumes
- Lane R's endpoints (`/api/recovery/options`, `/evaluate`, `/approve`), stubbed until R lands.
- Lane C's components and the Recovery Canvas.

## Provides
- A demo-safe build: honest error, stub, loading, and validation states.
- Live-API e2e evidence with screenshots in `frontend/e2e/screenshots/`.
- `scripts/freeze.sh` and `make freeze`.
- `docs/DEMO.md` and `docs/FIRST_PRINCIPLES.md`.

## Files to create
| Path | Purpose |
|---|---|
| `backend/tests/lane_h/test_errors.py` | 500s return a generic message with a request ID |
| `frontend/e2e/recovery.spec.ts` | The core recovery flow on mocks and on the live API |
| `frontend/src/api/client.test.ts` | ApiError parsing, stub detection, revision guard |
| `scripts/freeze.sh` | Regenerate generated files and mocks, then fail if git status is not clean |
| `docs/FIRST_PRINCIPLES.md` | Every parameter with value, unit, derivation, tag. Sanity checks. What would change our conclusions |

## Scope

### P0 (in order)
1. **500 errors**: a generic ApiError message with a request ID (also in the `X-Request-ID` header). Details go to the server log only.
2. **Late shipment removed** from README, `docs/DEMO.md`, `docs/CONTRACTS.md`, the demo recordings in `scripts/record_mocks.py`, and the recorded mocks. It stays in the API and the tests.
3. **Stub honesty**: `client.ts` exposes `isStub` from the payload `stub` field or the `X-Rollout-Stub` header. C shows a visible stub label (ask through NEEDS.md). An e2e check asserts the label while stubs are live.
4. **Validation honesty**: every plan the UI shows carries `validation.checked` and `validation.valid`. The UI says "Validated" only when both are true. Fix the stale "Not validated" expectations in `src/lib/export.test.ts` and `e2e/shell.spec.ts`.
5. **Error and loading states**: show the ApiError message, a progress line with text (never a bare spinner), and drop responses whose revision is older than the current one. Vitest for `client.ts` and the store.
6. **Live-API e2e** of the core recovery flow: load `standard`, apply a disruption, get options, select one, approve. Run with `VITE_API_MODE=live` against `make api`. Screenshots to `frontend/e2e/screenshots/`.
7. **Freeze script** `scripts/freeze.sh`: regenerate `contracts/openapi.json`, `frontend/src/api/generated.ts`, and all mocks from the in-process backend, then fail if `git status` is not clean. Add `make freeze`.

### P1
8. Accessibility pass: option cards and Approve reachable by keyboard, visible focus ring, AA contrast on the tokens, status never color alone. Automated check with axe or Playwright.
9. Performance at 1440x900 and 1920x1080: no layout overflow, local interactions under 100 ms, the evaluate progress line visible during about 2 s solves.
10. `docs/DEMO.md` recovery demo script (3 minutes). `docs/FIRST_PRINCIPLES.md` (every `config.parameters` entry with value, unit, derivation, tag. Sanity checks. What would change our conclusions). README known limitations.

### P2
11. Energy value upper-bound test.
12. Dark mode and reduced-motion audit.

## Definition of done
- The core recovery flow runs on the live API in Playwright, with screenshots.
- No response leaks exception text. Every stub and every unvalidated plan is labeled as such in the UI.
- `make freeze` leaves `git status` clean.
- Lane check passes (below). `make check-contracts`, `make check-a`, `make check-b` pass.

## Lane check
`cd backend && uv run pytest -q tests/lane_h tests/contract && cd ../frontend && pnpm typecheck && pnpm test && pnpm build`

## Cut list (cut in this order)
1. P2 items.
2. Performance audit.
3. Accessibility automation (keep the manual keyboard pass).
Never cut the 500 fix, stub honesty, validation honesty, or the live-API e2e.

## Working rules
- Branch `lane/H-hardening`. Pull `origin/main` at session start.
- Build on recorded mocks until the hour-4 sync. Then run the live e2e.
- One PR per feature item. Merge only after the checks and an evaluator PASS. Never push to `main`.
- Update `lanes/H-hardening/PROGRESS.md` after every item. Write requests to other lanes in `lanes/<their lane>/NEEDS.md`.
