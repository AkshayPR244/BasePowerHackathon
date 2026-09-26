# Lane W · Weather evidence and trust

## Mission
Rollout Planner is a deterministic disruption-recovery planner for installation operations. It shows what broke, how the disruption cascades through the current plan, what feasible recovery actions exist, what each costs or saves relative to doing nothing, and lets the operations manager review, test changes, and approve. R is the product, W is the evidence, C is the experience.

Lane W produces the evidence. It turns real Houston Hobby storm observations into modeled disruptions, replays the whole June–July 2018 season through the recovery engine, compares no action against recovery, and stress-tests the result. It also owns trust: honest wording, error handling, docs, and the freeze script.

Wording rule for every data file, API field, UI string, and doc: "This replay applies a modeled operational disruption to a real historical storm." Never imply a storm actually stopped any company's crews.

## Current state
- On `main`: the weather rule and METAR parser in `backend/app/data/weather.py` (`lost_reasons`), tested in `backend/tests/lane_a/test_first_principles.py`. Observed Hobby METAR files sit in gitignored `data/raw/weather/` with no manifest.
- Weekdays the rule marks as lost in June–July 2018: 06-14, 06-20, 06-25, 06-27, 06-28, 07-04 (holiday), 07-05, 07-09, 07-12, 07-31.
- July 4 2018 sums to 145 mm of METAR rain in work hours. Check for double-counted accumulations before you use it.
- Frozen in this scaffold: `StormEvent`, `Case`, `SeasonReplay`, `SeasonReplayEvent`, `SeasonTotals`, `StressTest` contracts. Stub service `backend/app/replay/service.py` (`storms()`, `cases()`, `season_replay()` read `backend/app/replay/fixtures/*.json`). Stub endpoints `GET /api/storms`, `/api/cases`, `/api/season-replay` with `stub=true` and the header `X-Rollout-Stub: true`.
- Known trust gaps on `main`: the 500 handler in `backend/app/api/main.py` (`_unexpected`) returns exception text to the client. "Late shipment" still appears in `README.md`, `docs/DEMO.md`, `docs/CONTRACTS.md`, `scripts/record_mocks.py`, and the recorded mocks.

## Owns
- `backend/app/replay/`
- `data/weather/`, `data/demo/cases/`
- `frontend/src/views/season/`
- `docs/` (shapes in `docs/CONTRACTS.md` change only through the change log), `README.md`
- Exception handlers in `backend/app/api/main.py`, and the `/api/storms`, `/api/cases`, `/api/season-replay` handlers
- `scripts/freeze.sh`, `scripts/record_mocks.py`
- `backend/tests/lane_w/`
- `lanes/W-evidence/`

## Must not touch
- `backend/app/recovery/`, `backend/app/planning/`, `backend/app/baselines/` (Lane R)
- `frontend/` outside `src/views/season/` (Lane C). Link to the canvas through the route Lane C provides.
- `backend/app/contracts/` except additive, logged changes

## Consumes
- `app.recovery.service.recover()` (the stub until the hour-4 sync, then Lane R's real engine). Call it exactly as frozen.
- `app.data.weather.lost_reasons`, `app.data.load.load_scenario`, `app.validate.validate_plan`.

## Provides
- `data/weather/` storm catalog with a manifest.
- `GET /api/storms`, `GET /api/cases`, `GET /api/season-replay` with `stub=false`.
- `docs/REPLAY_RESULTS.md`, `docs/FIRST_PRINCIPLES.md`, README known limitations.
- The Storm Season view.
- `scripts/freeze.sh`.

## Scope

### P0
1. **Storm event catalog** from real Hobby (IEM ASOS) observations: date, rainfall, wind, thunder hours, source URL, and retrieval date, with a manifest (sha256) in `data/weather/`.
2. **Weather → disruption rule** labeled "modeled" in data, API (`Case.modeled_rule`), UI copy, and docs.
3. **`GET /api/cases`** built from the catalog, feeding the canvas.
4. **Season replay** over every storm event in June–July 2018: no action vs `recover()`. Report events replayed, deadline misses under each, deadlines recovered, modeled cost under each, and median solve time. Use the stub `recover()` until the hour-4 sync.
5. **500 errors** return a generic message with a request ID. Log details server-side.
6. **Remove late shipment** from demo docs and demo mocks. Keep it in the API and tests.
7. **Validator status** exposed on everything the UI shows.

### P1
8. Storm Season view in `frontend/src/views/season/`: a strip of every day with real storm glyphs, season totals, play and scrub, click a storm to open it in the canvas.
9. Deterministic stress tests: durations +20%, travel +20%, weather rule looser and tighter. Report deadlines recovered and modeled advantage per variant.
10. `docs/REPLAY_RESULTS.md`, `docs/FIRST_PRINCIPLES.md`, and README known limitations.

### P2
11. Energy value upper-bound test.
12. 10-seed spread.
13. Freeze script: regenerate `openapi.json`, `generated.ts`, and all mocks from the live backend, then fail if `git status` is not clean.

## Definition of done
- Every storm event in the catalog comes from observed data with a manifest. Every case says its disruption is modeled.
- The season replay runs through the real `recover()` and reports every event, including ones where recovery does not help.
- No 500 response contains exception text.
- Lane check passes (below).

## Lane check
`cd backend && uv run ruff check app/replay tests/lane_w && uv run pytest -q tests/lane_w tests/contract`, plus `cd frontend && pnpm typecheck` when the season view changes.

## Cut list (cut in this order)
1. 10-seed spread.
2. Play animation (keep the static strip and click-through).
3. Weather threshold stress test.
Never cut the observed-data manifest, the "modeled" labels, or the error-handling fix.

## Working rules
- Branch `lane/W-evidence`. Pull `origin/main` at session start.
- Do not tune thresholds or windows to manufacture a win. Report results plainly.
- One PR per feature item. Merge only after the checks and an evaluator PASS. Never push to `main`.
- Update `lanes/W-evidence/PROGRESS.md` after every item. Write requests to other lanes in `lanes/<their lane>/NEEDS.md`.
