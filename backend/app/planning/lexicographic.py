"""Sequential lexicographic solves under one total time budget."""

import time
from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.contracts.enums import StageStatus
from app.contracts.models import StageMeta


@dataclass
class Stage:
    name: str
    maximize: bool = False
    max_s: float | None = None  # cap on this stage's share of the budget


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
    deadline = time.monotonic() + budget_s
    metas: list[StageMeta] = []
    snapshot: dict[str, int] | None = None
    all_vars = list(_named_vars(model))
    last_solver: cp_model.CpSolver | None = None

    for i, st in enumerate(stages):
        expr = exprs[st.name]
        remaining = deadline - time.monotonic()
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
        solver.parameters.max_time_in_seconds = remaining
        solver.parameters.random_seed = seed
        solver.parameters.num_workers = workers
        t0 = time.monotonic()
        code = solver.solve(model)
        elapsed = int((time.monotonic() - t0) * 1000)
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


def _named_vars(model: cp_model.CpModel):
    proto = model.proto
    for i, var in enumerate(proto.variables):
        if var.name:
            yield model.get_int_var_from_proto_index(i)
