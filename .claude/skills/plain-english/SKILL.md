---
name: plain-english
description: How this team writes UI copy, plan explanations, error messages, commit messages, PR descriptions, and docs. Use whenever you write any text a person reads, including PlanResult.message, UnscheduledJob.detail, PlanChange.note, PlanDiff.headline, CounterfactualResult.summary, UI labels, commits, PROGRESS.md, and NEEDS.md.
---

# Plain English

Simple technical English. Short sentences. Concrete numbers. Name the cause.

## Rules

1. One idea per sentence. Active voice. No semicolons.
2. Name the cause, then the effect, then the number. "Crew B is out Tuesday, so 3 North jobs move to Thursday. 1 misses its deadline."
3. Use numbers with units: "480 min", "1 day late", "$0 modeled value".
4. Use a verb, not a noun form: "compare plans", not "perform a comparison".
5. Use one name for one thing. Crew A is always "Crew A". A site ID is always the site ID.
6. Keep real uncertainty. "May" stays "may". Do not stack hedges.
7. Never claim what we did not measure. No "saves", "optimizes revenue", "guarantees".
8. No hype: robust, seamless, powerful, cutting-edge, leverage, AI-powered, revolutionary.
9. No phrasal verbs where a plain verb exists: "start", not "spin up". "Begin", not "kick off".
10. Label synthetic, modeled, and assumed data every time it appears.

## Product vocabulary

Rollout Planner is a planning and recovery analysis tool for residential battery installers. Use these words: plan, disruption, recovery, commitments, risk, impact, explanation.

- A crew out, a late shipment, or a slipped approval is a **disruption**. Adding a crew-day or forcing a job in is an **intervention**.
- The installer's existing plan is the **current plan**. Its rows are **planned installs**. Moved rows are **moved installs**.
- Never describe the product as booking, appointment picking, scheduling for customers, or backlog refinement.

## Good and bad

| Bad | Good |
|---|---|
| Leveraging advanced optimization, the plan was seamlessly adjusted. | Crew A is out Monday, so N-02 moves to Tuesday. It is 1 day late. |
| An error occurred. | No plan meets every deadline. N-02 is due Mon 4 Jun and no North crew works that day. |
| Solver returned status 3. | Timed out after 15 s before finding any plan. |
| Optimized for maximum value! | Energy value did not change any choice. All site values are equal. |
| Job could not be scheduled due to constraints. | S-03 needs skill panel_upgrade. No crew has it. |

## Plan text fields

- `PlanResult.message`: one or two sentences. The outcome, then the main cause.
- `UnscheduledJob.detail`: the hard blocker from data, in one sentence. A tight resource is not a proven cause. Say "did not fit in the available crew time" only when that is what the solver shows.
- `PlanChange.note`: "N-03 moves from Crew A Tue 5 Jun to Crew A Wed 6 Jun."
- `PlanDiff.headline`: counts first. "2 jobs move. 1 misses its deadline by 1 day."
- `CounterfactualResult.summary`: the intervention, then the result. "Adding Crew C on Monday makes N-02 on time. No job is late."

Date format in text: `Mon 4 Jun`. Times and IDs in mono in the UI.

## Commit messages

- Prefix with the lane: `lane-a: add input checks for duplicate IDs`.
- Imperative mood, under 72 characters in the subject.
- Body only when the why is not obvious. Plain sentences.
- No attribution lines. No emoji.

## PROGRESS.md and NEEDS.md

- Facts, not feelings. "Recovery stage 3 times out on standard at 15 s. Cut to 4 stages for now."
- Every blocker names what is needed and from whom.
