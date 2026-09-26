"""FastAPI app. Endpoints: docs/CONTRACTS.md and SPEC section 11."""

import asyncio

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.scenarios import load_scenario, scenario_ids, summarize
from app.compare.diff import diff_plans
from app.contracts.models import (
    ApiError,
    CompareRequest,
    CounterfactualRequest,
    CounterfactualResult,
    PlanDiff,
    PlanRequest,
    PlanResult,
    Scenario,
    ScenarioSummary,
)
from app.planning.counterfactual import counterfactual
from app.planning.solve import InvalidPlanError, plan

app = FastAPI(
    title="Rollout Planner API",
    description="Plan and disruption in, best recovery and its impact out.",
    version="1.0.0",
    separate_input_output_schemas=False,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ERRORS = {
    404: {"model": ApiError, "description": "Unknown scenario"},
    422: {"model": ApiError, "description": "Scenario files are invalid"},
    500: {"model": ApiError, "description": "The planner produced a plan that failed validation"},
}


class ApiException(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.error = status, ApiError(code=code, message=message)


@app.exception_handler(ApiException)
async def _api_error(_: Request, exc: ApiException) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.error.model_dump(mode="json"))


@app.exception_handler(InvalidPlanError)
async def _invalid_plan(_: Request, exc: InvalidPlanError) -> JSONResponse:
    err = ApiError(code="invalid_plan", message=str(exc))
    return JSONResponse(status_code=500, content=err.model_dump(mode="json"))


def _scenario(scenario_id: str) -> Scenario:
    if scenario_id not in scenario_ids():
        raise ApiException(404, "unknown_scenario", f"No scenario named {scenario_id}.")
    try:
        return load_scenario(scenario_id)
    except (ValueError, KeyError, OSError) as e:
        raise ApiException(422, "invalid_input", f"Scenario {scenario_id} did not load: {e}") from e


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/scenarios")
def list_scenarios() -> list[ScenarioSummary]:
    return [summarize(load_scenario(s)) for s in scenario_ids()]


@app.get("/api/scenarios/{scenario_id}", responses=ERRORS)
def get_scenario(scenario_id: str) -> Scenario:
    return _scenario(scenario_id)


@app.post("/api/plans", responses=ERRORS)
async def create_plan(req: PlanRequest) -> PlanResult:
    return await asyncio.to_thread(plan, _scenario(req.scenario_id), req)


@app.post("/api/plans/compare")
def compare_plans(req: CompareRequest) -> PlanDiff:
    if req.before.scenario_id != req.after.scenario_id:
        raise HTTPException(400, "Plans come from different scenarios.")
    return diff_plans(req.before, req.after)


@app.post("/api/plans/counterfactual", responses=ERRORS)
async def run_counterfactual(req: CounterfactualRequest) -> CounterfactualResult:
    return await asyncio.to_thread(counterfactual, _scenario(req.request.scenario_id), req)
