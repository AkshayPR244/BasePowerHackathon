# SlackLine UI

Operator workspace for installation plans, disruptions, recovery, and explanations. The default demo uses Lane B's recorded responses. It does not run an optimizer or contact customers.

## Deployed application

Open **[https://slackline.up.railway.app/](https://slackline.up.railway.app/)** for the hosted live-API build. Railway serves this Vite application and the FastAPI backend from one origin. The deployment uses representative synthetic portfolios and modeled disruptions for demonstration; it is not connected to customer, CRM, dispatch, or production operations data.

## Run

Use Node 24 and pnpm 11.25.0.

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Open http://localhost:5173. No API keys or backend needed. Fonts and recorded data are bundled locally.

For the API, start the backend on port 8000 and run `VITE_API_MODE=live pnpm dev`. Vite proxies `/api` to that port. Set this environment variable before building a live deployment as well; a static deployment must provide its own same-origin `/api` reverse proxy.

The repository's Railway deployment uses the root `Dockerfile` and `railway.json`, which build the frontend in live mode and serve it through the backend service. Check the deployed service at [`/api/health`](https://slackline.up.railway.app/api/health).

## Demonstrate

1. Inspect the initial strict plan and the blocked S-03 install.
2. Remove Crew A on the first day. The previous result stays visible with a hatch.
3. Select **Solve strict**. The scenario becomes infeasible.
4. Select **Find recovery**. N-02 becomes one day late.
5. Select **Compare plans** to see changes against the pinned original result.
6. Select N-02. Test requiring its deadline, then adding Crew C.
7. Export JSON or CSV. Reset to replay the demo.

Recorded mode supports exactly the requests in `src/mocks/recorded/index.json`. Unsupported requests return 501, never a fabricated result. Revisions are echoed and old responses are ignored. The recorded validator is a stub: the UI deliberately says **Not validated**. Live results that fail validation hide assignments and cannot be exported.

## Structure

- `src/api/`: OpenAPI-generated types and typed HTTP client.
- `src/state/store.ts`: edits, monotonically increasing revisions, selection, pinned baseline.
- `src/state/usePlanner.ts`: queries and asynchronous plan/compare/intervention lifecycle.
- `src/components/`: independent display panels; `src/views/Workspace.tsx` composes them.
- `src/design/`: tokens, styles, and the shared status glyphs.
- `src/mocks/`: MSW request matching; recorded files remain owned by Lane B.

## Check

```bash
make check-c # from repository root
./scripts/gen_types.sh # from repository root; regenerate after OpenAPI changes
cd frontend
pnpm exec playwright install chromium
pnpm e2e
pnpm format:check
```

Playwright saves screenshots under `e2e/screenshots`. If Chromium is already installed elsewhere, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to its executable. No system-specific path is committed.

## Current limits

- Crew-day removal is implemented. Inventory and readiness edits need additional UI controls and recordings.
- Plans have daily capacity, not arrival times or power-interruption windows.
- The tiny fixture has equal zero energy values; it does not prove arbitrage improvement.
- The original baseline is pinned until reset. There is no baseline replacement control yet.
- Adding Crew C assumes 480 minutes and the selected site's skill/cluster. This is a what-if intervention, not a verified available crew.
- No animated movement, command palette, authentication, or persistence. Customer confirmation remains outside scope.
- Live backend integration still depends on the data/planning branch fixes documented in the review.
