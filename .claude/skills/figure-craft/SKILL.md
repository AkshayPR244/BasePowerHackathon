---
name: figure-craft
description: Research-figure rules for the Rollout Planner live recovery canvas. Use when building or changing the crew/home plan figure or recovery-option frontier.
---

# Figure Craft

- Label series and marks directly where possible. Keep axes and labels legible at the target viewport.
- Use position and size before color to communicate value. Reserve the one alert accent for missed deadlines and validation failures.
- Show at most one movement path at a time, on hover or trace selection. Never draw all changed-visit paths together.
- Keep the plan and option frontier linked: selecting a frontier point updates the plan; selecting a visit identifies its home and option context.
- Make a changed plan visible through brief, cause-specific motion. Respect `prefers-reduced-motion` and avoid before/after slideshows.
- Derive every plotted value, coordinate, and label from scenario or recovery API data. Do not invent values for visual balance.
