# Lane C · Recovery Canvas · progress

## Continue from here

Any agent or person can pick this up cold. Rewrite this block before you stop.

- **Branch:** `lane/C-canvas`. Then `git fetch origin && git merge origin/main`.
- **Setup:** `cd frontend && pnpm install`
- **Check:** `cd frontend && pnpm typecheck && pnpm test && pnpm build`
- **Read first:** `AGENTS.md`, `CLAUDE.md` ("Product (read first)"), `lanes/C-canvas/BRIEF.md`, `docs/DESIGN.md`, `docs/CONTRACTS.md` (recovery shapes), `frontend/src/mocks/recorded/index.json`, `.claude/skills/design-system/SKILL.md`
- **Next:** C-01, render two-visit `standard` (key visits by `job_id ?? site_id`), then C-02 the disruption bar on the recorded `recovery_options_standard_storm` mock.
- **Then:** the next item in `lanes/C-canvas/feature_list.json` with `"passes": false`, highest priority first.

## Done
- Scaffold (2026-09-26): recovery mocks recorded (storm, case, and season-replay mocks too, but weather is parked). `generated.ts` regenerated with the recovery contracts.
- Already on `main` (PR #5): the tiny workspace.

## In progress
- None.

## Blockers
- None.
