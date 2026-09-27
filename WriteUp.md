# SlackLine

Field deployment is where plans meet messy reality. A crew is unavailable. Inventory arrives late. A customer is not ready. A schedule built around commitments becomes spreadsheets, uncertain calls, and customer disruption.

SlackLine is built for the deployment and operations manager keeping residential battery rollouts moving. It turns a disrupted field plan into a decision: what changed, which visits and battery appointments are at risk, and which recovery action protects commitments.

SlackLine solves a constrained recovery-planning problem. It models crew skills, capacity, service clusters, inventory timing, readiness, locked appointments, and the sequence between electrical installation and battery commissioning. When a disruption occurs, the system evaluates the no-action outcome, rebalances feasible work, and tests bounded additions such as overtime or temporary crew capacity.

A Python and FastAPI backend uses OR-Tools CP-SAT to optimize recovery priorities lexicographically: protect commitments first, reduce delay second, then minimize customer movement and travel while considering modeled battery operating value. An independent validator checks every plan before approval. The React workspace makes the reasoning visible through a crew calendar, impact cascade, recovery comparisons, and drill-down explanations.

The result: a recovery desk, a defensible way to turn “the plan broke” into an informed next move.

This hackathon prototype uses synthetic or modeled homes, crews, appointments, disruptions, and cost assumptions. Next, SlackLine can ingest live CRM updates, expand decision variables, derive costs from historical operations, and attach uncertainty ranges to estimates. Historical ERCOT prices remain a hindsight operating-value benchmark, never a forecast, production recommendation, or claim about Base operations.
