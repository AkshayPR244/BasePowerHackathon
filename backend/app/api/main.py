"""FastAPI app. Endpoints: docs/CONTRACTS.md and SPEC section 11."""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import warm
from app.api.scenarios import ScenarioLoadError, load_scenario, scenario_ids, summarize
from app.compare.diff import diff_plans
from app.contracts.models import (
    ApiError,
    ApproveRequest,
    ApproveResult,
    Case,
    CompareRequest,
    CounterfactualRequest,
    CounterfactualResult,
    EvaluateRequest,
    PlanDiff,
    PlanRequest,
    PlanResult,
    RecoveryOption,
    RecoveryOptionsRequest,
    RecoveryOptionsResult,
    Scenario,
    ScenarioSummary,
    SeasonReplay,
    StormEvent,
)
from app.planning.counterfactual import counterfactual
from app.planning.solve import InvalidPlanError, plan
from app.recovery import service as recovery
from app.replay import service as replay


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
    allow_origins=[f"http://{h}:{p}" for h in ("localhost", "127.0.0.1") for p in (5173, 4173)],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Rollout-Stub", "X-Request-ID"],
)

ERRORS = {
    400: {"model": ApiError, "description": "The request is valid JSON but makes no sense"},
    404: {"model": ApiError, "description": "Unknown scenario or path"},
    422: {"model": ApiError, "description": "The request or the scenario files are invalid"},
    500: {"model": ApiError, "description": "The planner produced a plan that failed validation"},
}


# Bounds keep one request from holding a solver worker for minutes.
MAX_EDITS = 200
MAX_REVISION = 2**53 - 1  # largest integer a JavaScript client can round-trip


class ApiException(Exception):
    def __init__(self, status: int, code: str, message: str, issues=(), headers=None):
        self.status = status
        self.error = ApiError(code=code, message=message, input_issues=list(issues))
        self.headers = headers or {}


def _json(status: int, err: ApiError) -> JSONResponse:
    return JSONResponse(status_code=status, content=err.model_dump(mode="json"))


@app.exception_handler(ApiException)
async def _api_error(_: Request, exc: ApiException) -> JSONResponse:
    response = _json(exc.status, exc.error)
    response.headers.update(exc.headers)
    return response


log = logging.getLogger("rollout.api")


def _logged(what: str, exc: BaseException) -> str:
    """Log the details server-side and return the request ID the client sees."""
    request_id = uuid.uuid4().hex[:12]
    log.error("request %s: %s", request_id, what, exc_info=exc)
    return request_id


def _server_error(code: str, exc: Exception) -> JSONResponse:
    """Log the details server-side. The client gets a generic message and a request ID."""
    request_id = _logged(f"failed with {code}", exc)
    message = f"The server could not complete this request. Request ID: {request_id}."
    response = _json(500, ApiError(code=code, message=message))
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(InvalidPlanError)
async def _invalid_plan(_: Request, exc: InvalidPlanError) -> JSONResponse:
    return _server_error("invalid_plan", exc)


@app.exception_handler(RequestValidationError)
async def _bad_request(_: Request, exc: RequestValidationError) -> JSONResponse:
    parts = []
    for e in exc.errors():
        if e.get("type") == "json_invalid":
            parts.append("The request body is not valid JSON.")
            continue
        where = ".".join(str(p) for p in e.get("loc", ()) if p != "body")
        parts.append(f"{where}: {e.get('msg')}" if where else str(e.get("msg")))
    return _json(422, ApiError(code="invalid_request", message="; ".join(parts)))


@app.exception_handler(StarletteHTTPException)
async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return _json(exc.status_code, ApiError(code=code, message=str(exc.detail)))


@app.exception_handler(Exception)
async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
    return _server_error("internal_error", exc)


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
        request_id = _logged(f"scenario {scenario_id} did not load", e)
        raise ApiException(
            422,
            "invalid_input",
            f"Scenario {scenario_id} did not load. Request ID: {request_id}.",
            headers={"X-Request-ID": request_id},
        ) from e


def _check_size(revision: int, **lists: list | None) -> None:
    if revision > MAX_REVISION:
        raise ApiException(422, "invalid_request", f"revision must be at most {MAX_REVISION}.")
    for name, items in lists.items():
        if items is not None and len(items) > MAX_EDITS:
            raise ApiException(
                422,
                "invalid_request",
                f"{name} has {len(items)} items. The limit is {MAX_EDITS}.",
            )


@app.get("/api/health")
def health() -> dict[str, str]:
    """`values` is not_started, warming, ready, or failed."""
    return {"status": "ok", **warm.status()}


@app.get("/api/scenarios")
def list_scenarios(response: Response) -> list[ScenarioSummary]:
    # A broken scenario is left out and named in a header. A docstring here would change the spec.
    good, broken = [], []
    for sid in scenario_ids():
        try:
            good.append(summarize(load_scenario(sid)))
        except Exception as e:  # noqa: BLE001 - one bad scenario must not hide the others
            _logged(f"scenario {sid} did not load", e)
            broken.append(sid)
    if broken:
        response.headers["X-Rollout-Broken-Scenarios"] = ",".join(broken)
    return good


@app.get("/api/scenarios/{scenario_id}", responses=ERRORS)
def get_scenario(scenario_id: str) -> Scenario:
    return _scenario(scenario_id)


@app.post("/api/plans", responses=ERRORS)
async def create_plan(req: PlanRequest) -> PlanResult:
    _check_size(req.revision, edits=req.edits)
    scenario = await asyncio.to_thread(_scenario, req.scenario_id)
    return await asyncio.to_thread(plan, scenario, req)


@app.post("/api/plans/compare", responses=ERRORS)
def compare_plans(req: CompareRequest) -> PlanDiff:
    if req.before.scenario_id != req.after.scenario_id:
        raise ApiException(400, "scenario_mismatch", "Plans come from different scenarios.")
    return diff_plans(req.before, req.after)


@app.post("/api/plans/counterfactual", responses=ERRORS)
async def run_counterfactual(req: CounterfactualRequest) -> CounterfactualResult:
    _check_size(req.request.revision, edits=req.request.edits)
    if req.base.scenario_id != req.request.scenario_id:
        raise ApiException(422, "scenario_mismatch", "The base plan comes from another scenario.")
    scenario = await asyncio.to_thread(_scenario, req.request.scenario_id)
    return await asyncio.to_thread(counterfactual, scenario, req)


# Stubbed seams. Each response sets X-Rollout-Stub while any part is still a stub.


def _mark(response: Response, stub: bool) -> None:
    if stub:
        response.headers["X-Rollout-Stub"] = "true"


def _raised_in_recovery(exc: BaseException) -> bool:
    tb = exc.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    return tb is not None and tb.tb_frame.f_globals.get("__name__", "").startswith("app.recovery")


def _recovery_error(exc: ValueError, scenario_id: str, client_plan: bool) -> ApiException:
    """Map the recovery engine's own input errors to 422. Re-raise anything else as a server bug."""
    if type(exc) is not ValueError or not _raised_in_recovery(exc):
        raise exc
    if not client_plan and "current plan" in str(exc).lower():
        # The client sent no current plan, so the stored plan is at fault, not the request.
        request_id = _logged(f"scenario {scenario_id} current plan rejected", exc)
        return ApiException(
            422,
            "invalid_input",
            f"The current plan stored in scenario {scenario_id} is not feasible. "
            f"Request ID: {request_id}.",
            headers={"X-Request-ID": request_id},
        )
    return ApiException(422, "invalid_recovery", str(exc))


async def _recovery_call(function, scenario_id: str, client_plan: bool, *args):
    try:
        return await asyncio.to_thread(function, *args)
    except ValueError as exc:
        raise _recovery_error(exc, scenario_id, client_plan) from exc


@app.post("/api/recovery/options", responses=ERRORS)
async def recovery_options(
    req: RecoveryOptionsRequest, response: Response
) -> RecoveryOptionsResult:
    _check_size(req.revision, disruption=req.disruption)
    s = await asyncio.to_thread(_scenario, req.scenario_id)
    out = await _recovery_call(
        recovery.recover,
        req.scenario_id,
        req.current_plan is not None,
        s.model_copy(update={"revision": req.revision}),
        req.disruption,
        req.current_plan,
        req.economics_overrides,
        req.interactive,
    )
    _mark(response, out.stub)
    return out.model_copy(update={"revision": req.revision})


@app.post("/api/recovery/evaluate", responses=ERRORS)
async def recovery_evaluate(req: EvaluateRequest, response: Response) -> RecoveryOption:
    _check_size(req.revision, disruption=req.disruption, interventions=req.interventions)
    s = await asyncio.to_thread(_scenario, req.scenario_id)
    out = await _recovery_call(
        recovery.evaluate,
        req.scenario_id,
        req.current_plan is not None,
        s.model_copy(update={"revision": req.revision}),
        req.disruption,
        req.interventions,
        req.current_plan,
        req.economics_overrides,
        req.interactive,
    )
    _mark(response, out.stub)
    return out


@app.post("/api/recovery/approve", responses=ERRORS)
def recovery_approve(req: ApproveRequest, response: Response) -> ApproveResult:
    _check_size(req.revision)
    try:
        out = recovery.approve(
            _scenario(req.scenario_id).model_copy(update={"revision": req.revision}), req.option
        )
    except ValueError as exc:
        raise _recovery_error(exc, req.scenario_id, True) from exc
    _mark(response, out.stub)
    return out


@app.get("/api/storms")
def list_storms(response: Response) -> list[StormEvent]:
    out = replay.storms()
    _mark(response, any(x.stub for x in out))
    return out


@app.get("/api/cases")
def list_cases(response: Response) -> list[Case]:
    out = replay.cases()
    _mark(response, any(x.stub for x in out))
    return out


@app.get("/api/season-replay")
def season_replay(response: Response) -> SeasonReplay:
    out = replay.season_replay()
    _mark(response, out.stub)
    return out
