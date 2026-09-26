# Demo script (3 minutes)

Rollout Planner is a planning and recovery analysis tool for residential battery installers. It takes an installation plan plus a disruption (crew out, late shipment, slipped approval), finds the best recovery, and explains what is at risk and why.

Source: SPEC section 14. Status: planned. Every step depends on lane work. Rehearse on the build you will show and fix this script to match what the app really does.

Use the `standard` scenario for the live demo if it is ready and validated. Use `tiny` as the fallback. `tiny` has known answers, so it cannot surprise you.

## Before you start
- Run the app on the live API (`make dev-live`, planned) or on recorded mocks (`make dev`, planned) if the backend is not ready. Say which one you use.
- Precompute the value table. Report its preparation time separately from solve time.
- Reset to the baseline (`make demo`, planned).
- Open the header provenance badge once to check it reads "Synthetic" where it should.

## Script

| Time | Action | Say |
|---|---|---|
| 0:00 | Load the scenario. Point at the header badge and dates. | "This is a synthetic benchmark: 30 candidate sites, 3 crews, 10 working days. Prices are 2018 ERCOT data, used as hindsight." (Tiny: "6 hand-built jobs, 2 crews, 3 days.") |
| 0:20 | Show the baseline plan and metrics. Point at a locked job and the blocked job. | "Every job meets its deadline. N-01 is a locked install in the current plan. S-03 needs a panel upgrade and no crew has that skill, so it is blocked." |
| 0:40 | Apply a disruption: remove a crew-day. The plan hatches and shows "previous result". | "Disruption: Crew A is out Monday. The old plan stays visible until the new one is ready." |
| 0:55 | Solve strict. It returns infeasible. | "No plan meets every commitment. N-02 is due Monday and Crew A is the only North crew." |
| 1:10 | Switch to recovery and solve. | "Recovery keeps crews, inventory, and locks as hard limits. It relaxes only deadlines." |
| 1:25 | Open the compare panel. | Read the impact headline: "2 jobs move. 1 misses its deadline by 1 day." Then one line: "N-02 moves to Tuesday, 1 day late. N-03 moves to Wednesday to make room." |
| 1:50 | Select N-02 in the deferred list or calendar. Open the inspector. Run the intervention "include by deadline". | "Forcing N-02 by Monday is infeasible. Adding a North crew on Monday fixes it." Run the intervention "add crew-day" and show all commitments met. |
| 2:20 | Show baseline versus optimized operating value. | State the measured result. If `value_distinguishes_choices` is false: "Energy value did not change the recovery plan in this case." |
| 2:40 | Export JSON and CSV. | "The export has assignments, missed commitments, assumptions, and solver status." |
| 2:50 | Close. | "Every plan you saw passed an independent validator." Say this only if every plan showed validated. |

## Honesty checklist

Check each before recording:

- [ ] Say whether the energy-aware objective changed the plan. If it did not, say so.
- [ ] Every synthetic input is labeled "Synthetic" in the UI and in speech.
- [ ] Prices are called "2018 hindsight prices", never a forecast.
- [ ] Value is "modeled operating margin", never profit, revenue, savings, or ROI.
- [ ] Every plan shown says validated. If one says "Not validated", say so or cut it.
- [ ] Solve times quoted are measured on the demo machine. Say "on this laptop".
- [ ] Parcels are "candidate locations", not customers.
- [ ] Travel is "a fixed allowance per crew-day", not routed drive time.
- [ ] No claim that Base lacks such a tool.
- [ ] Mocks versus live API: say which one the recording uses.
