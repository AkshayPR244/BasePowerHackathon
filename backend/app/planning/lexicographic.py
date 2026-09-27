"""Sequential lexicographic solves under one total time budget."""

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.contracts.enums import StageStatus
from app.contracts.models import StageMeta


@dataclass
class Stage:
    name: str
    maximize: bool = False
    max_s: float | None = None  # cap on this stage's share of the budget


@dataclass(frozen=True)
class Tuning:
    """Optional per-call solver settings for callers that cannot pass arguments through plan()."""

    hint: dict[str, int] | None = None  # full warm start; unnamed x_, a_, y_ variables get 0
    deterministic: bool = False  # budget counts deterministic time, so reruns match
    wall_factor: float = 3.0  # wall-clock safety cap as a multiple of the budget


_tuning: ContextVar[Tuning | None] = ContextVar("solve_tuning", default=None)


@contextmanager
def tuned(tuning: Tuning):
    token = _tuning.set(tuning)
    try:
        yield
    finally:
        _tuning.reset(token)


@dataclass
class LexResult:
    stages: list[StageMeta]
    values: dict[str, int] | None  # variable name -> value from the last good solve
    solver: cp_model.CpSolver | None


_STATUS = {
    cp_model.OPTIMAL: StageStatus.optimal,
    cp_model.FEASIBLE: StageStatus.feasible,
    cp_model.INFEASIBLE: StageStatus.infeasible,
    cp_model.UNKNOWN: StageStatus.timeout_no_incumbent,
}


def _gap(value: float, bound: float) -> float:
    return abs(value - bound) / max(1.0, abs(value))


def solve_stages(
    model: cp_model.CpModel,
    exprs: dict[str, cp_model.LinearExpr],
    stages: list[Stage],
    budget_s: float,
    seed: int,
    workers: int,
) -> LexResult:
    """Solve stages in order. Each later stage keeps earlier stages at their achieved value."""
    tuning = _tuning.get() or Tuning()
    det = tuning.deterministic
    deadline = time.monotonic() + budget_s * (tuning.wall_factor if det else 1)
    det_left = budget_s
    metas: list[StageMeta] = []
    snapshot: dict[str, int] | None = None
    all_vars = list(_named_vars(model))
    last_solver: cp_model.CpSolver | None = None
    if det:
        _canonical_order(model)
    if tuning.hint is not None:
        model.clear_hints()
        for v in all_vars:
            if v.name in tuning.hint:
                model.add_hint(v, tuning.hint[v.name])
            elif v.name.startswith(("x_", "a_", "y_")):
                model.add_hint(v, 0)

    for i, st in enumerate(stages):
        expr = exprs[st.name]
        remaining = det_left if det else deadline - time.monotonic()
        if i < len(stages) - 1:
            # Leave time for later stages: one hard stage must not starve the ones after it.
            remaining = remaining / 2
        if st.max_s is not None:
            remaining = min(remaining, st.max_s)
        if remaining <= 0.01:
            metas += [
                StageMeta(name=s.name, status=StageStatus.skipped, elapsed_ms=0) for s in stages[i:]
            ]
            break
        constant = isinstance(expr, int)
        if constant and snapshot is not None:
            metas.append(
                StageMeta(
                    name=st.name,
                    status=StageStatus.optimal,
                    value=float(expr),
                    bound=float(expr),
                    gap=0.0,
                    elapsed_ms=0,
                )
            )
            continue
        model.clear_objective()
        if constant:
            pass  # nothing to optimize, but no stage has proved feasibility yet
        elif st.maximize:
            model.maximize(expr)
        else:
            model.minimize(expr)
        solver = cp_model.CpSolver()
        if det:
            solver.parameters.max_deterministic_time = remaining
            solver.parameters.max_time_in_seconds = max(0.05, deadline - time.monotonic())
            solver.parameters.interleave_search = workers > 1
        else:
            solver.parameters.max_time_in_seconds = remaining
        solver.parameters.random_seed = seed
        solver.parameters.num_workers = workers
        t0 = time.monotonic()
        code = solver.solve(model)
        elapsed = int((time.monotonic() - t0) * 1000)
        if det:
            det_left -= solver.response_proto.deterministic_time
        if code == cp_model.MODEL_INVALID:
            raise RuntimeError("CP-SAT rejected the generated model: " + model.validate())
        status = _STATUS[code]

        if status in (StageStatus.infeasible, StageStatus.timeout_no_incumbent):
            if snapshot is not None and status == StageStatus.timeout_no_incumbent:
                # Earlier stages hold a solution. Keep it and stop refining.
                metas.append(StageMeta(name=st.name, status=status, elapsed_ms=elapsed))
                metas += [
                    StageMeta(name=s.name, status=StageStatus.skipped, elapsed_ms=0)
                    for s in stages[i + 1 :]
                ]
                break
            metas.append(StageMeta(name=st.name, status=status, elapsed_ms=elapsed))
            metas += [
                StageMeta(name=s.name, status=StageStatus.skipped, elapsed_ms=0)
                for s in stages[i + 1 :]
            ]
            return LexResult(stages=metas, values=snapshot, solver=last_solver)

        if constant:
            value = bound = float(expr)
        else:
            value = float(round(solver.objective_value)) + 0.0
            bound = float(round(solver.best_objective_bound)) + 0.0
        metas.append(
            StageMeta(
                name=st.name,
                status=status,
                value=value,
                bound=bound,
                gap=_gap(value, bound),
                elapsed_ms=elapsed,
            )
        )
        achieved = round(value)
        if constant:
            pass
        elif st.maximize:
            model.add(expr >= achieved)
        else:
            model.add(expr <= achieved)
        snapshot = {v.name: solver.value(v) for v in all_vars}
        model.clear_hints()
        for v in all_vars:
            model.add_hint(v, snapshot[v.name])
        last_solver = solver

    return LexResult(stages=metas, values=snapshot, solver=last_solver)


def _canonical_order(model: cp_model.CpModel) -> None:
    """Sort constraints so a model built in hash-seeded set order searches the same way."""
    proto = model.proto
    if any(c.has_interval() for c in proto.constraints):
        return  # other constraints refer to intervals by position
    texts = sorted(str(c) for c in proto.constraints)
    proto.constraints.clear()
    for text in texts:
        proto.constraints.add().parse_text_format(text)


def _named_vars(model: cp_model.CpModel):
    proto = model.proto
    for i, var in enumerate(proto.variables):
        if var.name:
            yield model.get_int_var_from_proto_index(i)
