"""Find jobs that cannot all meet their deadlines together, via assumption literals."""

from collections.abc import Sequence

from ortools.sat.python import cp_model

from app.contracts.enums import Mode
from app.contracts.models import Edit, Scenario
from app.planning.edits import restrict_appointments
from app.planning.model import build, eligibility

MAX_CORE_S = 2.0  # the core only explains a failure, so cap its wait


def conflicting_jobs(
    scenario: Scenario, forced: set[str], budget_s: float, edits: Sequence[Edit] = ()
) -> list[str] | None:
    """Return a set of jobs whose on-time completion is jointly infeasible, or None.

    One assumption literal per job means "this job finishes by its deadline". CP-SAT returns
    a subset of them that is already infeasible. The subset is sufficient, not minimal.
    With `forced`, only forced homes must finish on time. Without it, every home must.
    """
    elig = restrict_appointments(eligibility(scenario, Mode.recovery, set()), edits)
    pm = build(scenario, elig, Mode.recovery, set(), {})
    if pm.lock_conflicts:
        return None
    sites = {s.site_id: s for s in scenario.sites}
    lits: dict[int, str] = {}
    for jid, job in elig.jobs.items():
        if not job.final or (forced and job.site_id not in forced):
            continue
        sid = job.site_id
        on_time = [v for (j, _, d), v in pm.x.items() if j == jid and d <= sites[sid].deadline]
        lit = pm.model.new_bool_var(f"ontime_{sid}")
        pm.model.add(sum(on_time) == 1).only_enforce_if(lit)
        lits[lit.index] = sid
    pm.model.add_assumptions([pm.model.get_bool_var_from_proto_index(i) for i in lits])
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1  # cores need a single worker
    solver.parameters.max_time_in_seconds = min(budget_s, MAX_CORE_S)
    solver.parameters.random_seed = scenario.config.random_seed
    if solver.solve(pm.model) != cp_model.INFEASIBLE:
        return None
    core = solver.sufficient_assumptions_for_infeasibility()
    return sorted(lits[i] for i in core if i in lits) or None
