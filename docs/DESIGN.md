# Design

Goal: a planning and recovery analysis console that feels like an internal tool a sharp infrastructure startup uses every day. Serious, dense, calm, with a point of view. A judge should think "hire them", not "nice template".

## Tokens

All color comes from CSS variables in `frontend/src/design/tokens.css`. Tailwind v4 reads them through `@theme`. Dark mode redefines the same names under `[data-theme="dark"]` and `prefers-color-scheme: dark`.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--paper` | `#F5F1E8` | `#15140F` | page background |
| `--panel` | `#FBF8F1` | `#1C1B16` | panels, calendar cells |
| `--ink` | `#1B1A17` | `#ECE7DA` | primary text |
| `--ink-2` | `#5A564D` | `#A9A396` | secondary text |
| `--hairline` | `#DAD3C4` | `#2E2C25` | 1 px borders |
| `--accent` | `#C4470A` | `#FF7A2E` | primary action, at-risk emphasis only |
| `--st-scheduled` | `#2F6F4F` | `#5DBB8A` | scheduled |
| `--st-locked` | `#3B4A6B` | `#8FA3CC` | locked |
| `--st-late` | `#8A6508` | `#E0B04A` | late |
| `--st-unscheduled` | `#6B6558` | `#9A9384` | unscheduled |
| `--st-blocked` | `#9B2C2C` | `#E06C6C` | blocked |

The accent never marks status. Status colors never mark actions.

## Type

- UI: IBM Plex Sans. IDs, dates, times, numbers: IBM Plex Mono. Both from `@fontsource`, so the app works offline.
- `font-variant-numeric: tabular-nums` on every value that can change.
- Scale (px): 11 label, 12 dense table, 13 body, 15 panel title, 20 metric value. No larger text anywhere.

## Layout

4 px grid. 1 px hairline borders. Radius 6 px max. No shadows except a 1 px focus ring. No gradients, no glass, no hero.

```text
┌ Header: scenario · [Synthetic data] · 4–6 Jun 2018 · policy · ● Optimal · Not validated ┐
├ Metrics: on time 5 │ late 0 │ unscheduled 1 (1 blocked) │ value $0 · equal │ util 41% │ moved installs 0 ┤
├──────────────────────────────── Calendar ─────────────────────────┬── Inspector ──────┤
│ Crew A │ Mon ▮▮▯ N-02         │ Tue ▮▮▮ 🔒N-01 N-03 │ Wed —       │ N-02              │
│ Crew B │ Mon ▮▮▮ S-01 S-02    │ Tue —               │ Wed —       │ ready Mon 4 Jun   │
├──────────────────────────────── Map (SVG) ───────┬─ Deferred ─────┤ due  Mon 4 Jun    │
│ cluster outlines + site points                   │ ■ S-03 blocked │ reasons, actions  │
└──────────────────────────────────────────────────┴────────────────┴───────────────────┘
```

The lock above is illustrative. The real UI uses the inline SVG lock icon, never an emoji.

## Status

Status is never color alone. Every status has a shape, a label, and a color.

| State | Shape | Label |
|---|---|---|
| scheduled | filled circle | Scheduled |
| locked | lock icon | Locked |
| late | triangle | Late · N days |
| unscheduled | hollow circle | Unscheduled |
| blocked | filled square | Blocked |

Plan status in the header: Optimal, Feasible (gap N%), Infeasible, Timed out (no plan found), Invalid input. Validation: "Validated", "N violations", or "Not validated" when `validation.checked` is false.

## Motion

- 150 to 250 ms, ease-out. Nothing loops.
- A re-plan animates each moved job from its old calendar cell to the new one, then highlights it for 1.5 s.
- Editing marks the result stale: a subtle diagonal hatch and a "Previous result" label until the new result arrives.
- Loading always has text: "Solving · stage 2 of 5 · 1.2 s". No bare spinner.
- `prefers-reduced-motion`: no movement. Highlights only.

## Details that carry the personality

- The map draws our own cluster outlines and site points in SVG. No stock tiles.
- The compare panel reads like a changelog: "N-02 moves Crew A Mon → Tue. 1 day late."
- Keyboard: `R` re-solve, `C` compare, `/` search, `Esc` clear selection.
- Microcopy follows the `plain-english` skill.

## Bans

Unmodified shadcn or Tailwind defaults. Purple-blue gradients. Centered card grids. Lorem ipsum. "AI-powered" or any hype word. Emoji. Bare spinners. Status shown by color alone.
