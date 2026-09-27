# Team and agent workflow (internal)

This file keeps team coordination notes that do not belong in the final submission README.

## Lane workflow

Three lanes build in parallel:

- `lane/R-engine`: recovery engine
- `lane/C-canvas`: recovery canvas UI
- `lane/H-hardening`: demo-safe behavior, errors, stubs, validation honesty, and e2e

Weather replay is parked in `lanes/_parked/weather`.

Rules and lane state:

- Global rules: `AGENTS.md` and `CLAUDE.md`
- Lane status: `lanes/<lane>/PROGRESS.md`
- Cross-lane steering: `STEER.md` or `lanes/<lane>/STEER.md`

Start a lane:

```bash
git switch lane/R-engine      # or lane/C-canvas, lane/H-hardening
./lanes/R-engine/init.sh
```

Agent prompt:

```text
Read AGENTS.md and CLAUDE.md, then lanes/R-engine/PROGRESS.md, and continue from there.
```

Agent controls:

- Stop all agents: `touch AGENT_STOP`
- Resume: `rm AGENT_STOP`

History:

- Day 1 lanes (A, B, C) are archived in `lanes/_archive/`.
