"""FastAPI app. Lane B owns it. Endpoints: docs/CONTRACTS.md and SPEC section 11."""

from fastapi import FastAPI

app = FastAPI(
    title="Rollout Planner API",
    description="Plan and disruption in, best recovery and its impact out.",
    version="1.0.0",
    separate_input_output_schemas=False,
)

# TODO(lane-b): GET /api/scenarios, GET /api/scenarios/{id}, POST /api/plans,
# POST /api/plans/compare, POST /api/plans/counterfactual.
