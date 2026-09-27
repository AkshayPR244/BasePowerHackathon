# Demo script (3 minutes)

Rollout Planner is a deterministic disruption-recovery planner for installation operations. It shows what broke, how the disruption cascades through the current plan, what recovery actions exist, what each costs or saves compared with no action, and lets the operations manager test changes and approve.

Rehearse on the build you will show. Change this script to match what the app does on that build.

## The case

- Scenario `standard`. It is synthetic. 45 homes, 90 visits: each home has an install (the electrical disconnect visit) and a battery day (the battery placement visit). 3 crews: IA and IB do installs, BA does battery days. Planning window Mon 4 Jun to Fri 15 Jun 2018.
- Disruption: all three field crews are out on Thu 14 Jun. This is a modeled operational disruption. It is not a weather event. Do not say a storm caused it.
- Energy value uses 2018 ERCOT prices as hindsight, not a forecast.
- Economics: the wage is the BLS OEWS May 2023 Houston electrician mean wage (observed). Crew size, overtime multiplier, temporary crew cost, and the overtime cap are assumed. The assumptions panel shows each tag.

## Before you start

- Run on the live API: `make dev-live`. If the backend is down, run on recorded mocks: `make dev`. Say which one you use.
- Open `http://localhost:8000/api/health`. Wait until `values` is `ready`.
- Run the recovery flow once before recording, so the value table is warm.

## Script

| Time | Action | Say |
|---|---|---|
| 0:00 | Load `standard`. Point at the synthetic label and the dates. | "A synthetic two-week plan: 45 homes, 90 visits, 3 crews." |
| 0:15 | Show the current plan in the crew calendar. | "Each home needs an install, then a battery day at least one business day later." |
| 0:30 | Apply the disruption: all crews out Thu 14 Jun. | "A modeled disruption: every field crew is out on Thursday." |
| 0:45 | Read the disruption bar and the cascade strip. Click a cascade step. | Read the impact headline. "<n> visits lose their day. <n> commitments are at risk if we do nothing." |
| 1:05 | Show the option cards: no action, rebalance, and any paid option the engine returns. | "Each option is a business action. Each one is solved and checked by an independent validator." |
| 1:30 | Compare net impact, deadlines missed, and customers to reschedule. Point at "Lowest modeled cost". | "Every crew is booked after Thursday, so rebalancing cannot help. A temporary battery crew on Friday recovers <n> deadlines and costs $<n> less than doing nothing." |
| 1:55 | Open the assumptions panel. Change one assumed number. | "Every cost has a source or the tag assumed. Change one and the ranking updates." |
| 2:15 | Test a change: pick Crew BA, add overtime on Fri 15 Jun. | "Overtime on Friday does not help. Crew BA works the West cluster that day and the lost visits are in the South. I can test my own change before I commit to it." |
| 2:35 | Select an option. Approve it. Read the confirm summary. | "Approval updates the plan for this analysis. It contacts no customers." |
| 2:50 | Close. | "Every plan you saw passed the independent validator." Say this only if every plan showed Validated. |

The engine returns an overtime or temporary-capacity option only when it helps more than no action and rebalance. Do not promise all four option kinds.

## Numbers

Fill each `<n>` from the build you record. Recovery solves use a deterministic work limit, so the same build gives the same plans. Solve times still vary by machine.

One reference run: 2026-09-26, branch `integrate/qa-fixes`, in-process API (`TestClient`) on a development laptop, `interactive: false`.

| Item | Measured |
|---|---|
| Impact | 7 visits affected, 1440 capacity minutes lost, 7 commitments at risk under no action |
| No action | net impact $630.25, 7 deadlines missed, 7 customers to reschedule |
| Rebalance existing crews | same plan as no action. No visit before Thu 14 Jun may move, and every crew is full after it. |
| Add temporary crew TEMP-BA on Fri 15 Jun (Lowest modeled cost) | net impact $458.40, $171.85 better than no action, 4 deadlines missed, 3 deadlines recovered, 7 customers to reschedule |
| Overtime option | not returned. Overtime before Thu 14 Jun is in the past, and overtime on Fri 15 Jun does not help. |
| Options solve time | 0.6 s for the first call, 0.05 s cached |
| Change the hourly wage to $35 | 0.06 s. Re-prices without a re-solve. Temporary crew becomes $565.12. |
| Test a change: Crew BA +120 min overtime Fri 15 Jun | 0.2 s, net impact $800.23, 7 deadlines missed |

## Honesty checklist

- [ ] Say "synthetic" for the scenario and "modeled" for the disruption.
- [ ] No weather claims. The disruption is modeled, not observed.
- [ ] Prices are "2018 hindsight prices", never a forecast.
- [ ] Value is "modeled operating margin", never profit, revenue, savings, or ROI.
- [ ] Say "customers to reschedule", not "changed installs". Say "Lowest modeled cost", not "Recommended".
- [ ] Every plan shown says Validated. If one says "Not validated", say so or cut it.
- [ ] Quote solve times only from the demo machine. Say "on this laptop".
- [ ] Say whether the recording uses the live API or recorded mocks.
- [ ] Approval does not contact customers and does not persist across API sessions.
