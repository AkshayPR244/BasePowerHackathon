"""FastAPI app. Endpoints: docs/CONTRACTS.md and SPEC section 11."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import warm
from app.api.scenarios import ScenarioLoadError, load_scenario, scenario_ids, summarize
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    warm.start()
    yield


app = FastAPI(
    title="Rollout Planner API",
    description="Plan and disruption in, best recovery and its impact out.",
    version="1.0.0",
    separate_input_output_schemas=False,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ERRORS = {
    400: {"model": ApiError, "description": "The request is valid JSON but makes no sense"},
    404: {"model": ApiError, "description": "Unknown scenario or path"},
    422: {"model": ApiError, "description": "The request or the scenario files are invalid"},
    500: {"model": ApiError, "description": "The planner produced a plan that failed validation"},
}


class ApiException(Exception):
    def __init__(self, status: int, code: str, message: str, issues=()):
        self.status = status
        self.error = ApiError(code=code, message=message, input_issues=list(issues))


def _json(status: int, err: ApiError) -> JSONResponse:
    return JSONResponse(status_code=status, content=err.model_dump(mode="json"))


@app.exception_handler(ApiException)
async def _api_error(_: Request, exc: ApiException) -> JSONResponse:
    return _json(exc.status, exc.error)


@app.exception_handler(InvalidPlanError)
async def _invalid_plan(_: Request, exc: InvalidPlanError) -> JSONResponse:
    return _json(500, ApiError(code="invalid_plan", message=str(exc)))


@app.exception_handler(RequestValidationError)
async def _bad_request(_: Request, exc: RequestValidationError) -> JSONResponse:
    parts = []
    for e in exc.errors():
        where = ".".join(str(p) for p in e.get("loc", ()) if p != "body")
        parts.append(f"{where}: {e.get('msg')}" if where else str(e.get("msg")))
    return _json(422, ApiError(code="invalid_request", message="; ".join(parts)))


@app.exception_handler(StarletteHTTPException)
async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return _json(exc.status_code, ApiError(code=code, message=str(exc.detail)))


def _scenario(scenario_id: str) -> Scenario:
    if scenario_id not in scenario_ids():
        raise ApiException(404, "unknown_scenario", f"No scenario named {scenario_id}.")
    try:
        return load_scenario(scenario_id)
    except ScenarioLoadError as e:
        raise ApiException(
            422, "invalid_input", f"Scenario {scenario_id} has input errors.", e.issues
        ) from e
    except (ValueError, KeyError, OSError) as e:
        raise ApiException(422, "invalid_input", f"Scenario {scenario_id} did not load: {e}") from e


@app.get("/api/health")
def health() -> dict[str, str]:
    """`values` is not_started, warming, ready, or failed."""
    return {"status": "ok", **warm.status()}


@app.get("/api/scenarios")
def list_scenarios() -> list[ScenarioSummary]:
    return [summarize(load_scenario(s)) for s in scenario_ids()]


@app.get("/api/scenarios/{scenario_id}", responses=ERRORS)
def get_scenario(scenario_id: str) -> Scenario:
    return _scenario(scenario_id)


@app.post("/api/plans", responses=ERRORS)
async def create_plan(req: PlanRequest) -> PlanResult:
    return await asyncio.to_thread(plan, _scenario(req.scenario_id), req)


@app.post("/api/plans/compare", responses=ERRORS)
def compare_plans(req: CompareRequest) -> PlanDiff:
    if req.before.scenario_id != req.after.scenario_id:
        raise ApiException(400, "scenario_mismatch", "Plans come from different scenarios.")
    return diff_plans(req.before, req.after)


@app.post("/api/plans/counterfactual", responses=ERRORS)
async def run_counterfactual(req: CounterfactualRequest) -> CounterfactualResult:
    return await asyncio.to_thread(counterfactual, _scenario(req.request.scenario_id), req)
