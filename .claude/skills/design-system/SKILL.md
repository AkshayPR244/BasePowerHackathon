---
name: design-system
description: Visual and interaction rules for the Rollout Planner UI. Use whenever you create or change anything under frontend/src (components, views, tokens, styles, copy, motion) or review UI screenshots. Points to docs/DESIGN.md and lists the component rules that every screen must follow.
---

# Design system

Read `docs/DESIGN.md` first. It is the full direction. This skill lists the rules you check on every component.

Target feel: an internal dispatch or trading console at a serious infrastructure startup. Dense, calm, exact.

## Tokens

- All colors, fonts, spacing, radii, and durations come from CSS variables in `frontend/src/design/tokens.css`. No raw hex in components.
- Tailwind v4 reads the tokens. Do not use Tailwind's default palette classes (`bg-blue-500`, `text-gray-700`).
- Light mode: warm paper background, ink text. Dark mode uses the same token names.
- One accent: signal orange. Use it only for the primary action and at-risk emphasis.
- Status colors are a separate palette from the accent.

## Type

- IBM Plex Sans for UI text. IBM Plex Mono for IDs, dates, times, minutes, and money.
- `font-variant-numeric: tabular-nums` on every value that changes.
- Fonts are self-hosted via `@fontsource`. The app works offline.

## Layout

- 4 px grid. Spacing is a multiple of 4.
- 1 px hairline borders separate regions. Radius 6 px maximum.
- No shadows (a 1 px focus ring is fine). No gradients. No glass or blur.
- Dense tables and rows. No hero sections, no centered card grids, no marketing copy.

## Status

Status is never color alone. Every status has shape + label + color.

| JobState | Shape | Label |
|---|---|---|
| `scheduled` | filled circle | Scheduled |
| `locked` | lock icon | Locked |
| `late` | triangle | Late |
| `unscheduled` | hollow circle | Unscheduled |
| `blocked` | square | Blocked |

Render status through `src/design/status.tsx` only.

## Solve and stale state

- Show solve status in words: Optimal, Feasible, Infeasible, Timed out (no plan), Invalid input.
- If `validation.checked` is false, show "Not validated" next to the status.
- An edit marks the result stale: subtle diagonal hatch over the plan plus a "previous result" label. Keep the old plan visible until the new one arrives.
- No bare spinners. Progress always has text: "Solving recovery plan, stage 2 of 5".

## Motion

- 150 to 250 ms. Motion shows cause: a re-planned job moves from its old cell to its new cell and briefly highlights.
- Respect `prefers-reduced-motion`: no movement, keep the highlight.

## Bans

Unmodified shadcn or Tailwind defaults, purple-blue gradients, emoji, lorem ipsum, "AI-powered" language, drop shadows on cards, icons without labels for status.

## Copy

Use the `plain-english` skill. Name the cause and the number: "Crew A is out Monday, so N-02 moves to Tuesday. 1 day late."
