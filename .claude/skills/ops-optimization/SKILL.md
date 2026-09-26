---
name: ops-optimization
description: CP-SAT plan and recovery optimization and HiGHS battery-valuation patterns for this repo. Use when writing or debugging backend/app/planning, backend/app/baselines, backend/app/validate/enumerate_tiny.py, or backend/app/valuation. Covers variable pruning, cluster channeling, cumulative inventory, lexicographic stages under one time budget, status mapping, hints, infeasibility explanation, running solves off the event loop, and the scipy.optimize.milp battery model with its test list.
---

# Ops optimization

Two solvers. Do not swap them.
- Plan and recovery optimization: OR-Tools CP-SAT (`ortools.sat.python.cp_model`).
- Battery valuation: SciPy `milp` (HiGHS). It needs continuous energy plus a binary mode.

Spec: `docs/SPEC.md` sections 6 and 7. Contracts: `backend/app/contracts/models.py`.

## 1. Variables: create only legal triples

A job may use (day d, crew r) only if the crew-day exists, the crew has the skill, the cluster is allowed, and `d >= ready_date`. In strict mode (or for a `ForceInclude` job) also `d <= deadline`. Never create a variable and then force it to 0.

```python
from ortools.sat.python import cp_model

model = cp_model.CpModel()
x: dict[tuple[str, date, str], cp_model.IntVar] = {}
options: dict[str, list[tuple[date, str]]] = {}
for s in scenario.sites:
    for cd in scenario.crew_days:
        if (s.required_skill in cd.skills and s.cluster_id in cd.allowed_clusters
                and cd.date >= s.ready_date
                and (not must_meet_deadline(s) or cd.date <= s.deadline)):
            x[s.site_id, cd.date, cd.crew_id] = model.new_bool_var(f"x_{s.site_id}_{cd.date}_{cd.crew_id}")
            options.setdefault(s.site_id, []).append((cd.date, cd.crew_id))
```

A job with no option before the deadline filter is `blocked` (explain it, do not add it). A job whose options all vanish after the deadline filter makes strict infeasible.

## 2. Assignment and cluster channeling

```python
assigned = {}
for sid, opts in options.items():
    vs = [x[sid, d, r] for d, r in opts]
    if strict:
        model.add_exactly_one(vs)
    else:
        assigned[sid] = model.new_bool_var(f"a_{sid}")
        model.add(sum(vs) == assigned[sid])

# y[r, d, k] = crew r works cluster k on day d
y = {}
for cd in scenario.crew_days:
    ks = sorted({site[sid].cluster_id for (sid, d, r) in x if (d, r) == (cd.date, cd.crew_id)})
    for k in ks:
        y[cd.crew_id, cd.date, k] = model.new_bool_var(f"y_{cd.crew_id}_{cd.date}_{k}")
    model.add_at_most_one(y[cd.crew_id, cd.date, k] for k in ks)
for (sid, d, r), v in x.items():
    model.add_implication(v, y[r, d, site[sid].cluster_id])
```

`add_implication(x, y)` is enough. A `y` without jobs only costs travel, so the travel stage turns it off.

## 3. Capacity with travel

```python
for cd in scenario.crew_days:
    onsite = sum(site[sid].duration_min * v for (sid, d, r), v in x.items() if (d, r) == (cd.date, cd.crew_id))
    travel = sum(travel_min[k] * y[r, d, k] for (r, d, k) in y if (r, d) == (cd.crew_id, cd.date))
    model.add(onsite + travel <= cd.available_min)
```

## 4. Cumulative inventory

Receipts are incoming quantities. By each working day, installs so far must not exceed receipts so far, per configuration.

```python
for cfg in configs:
    for day in working_days:
        used = sum(v for (sid, d, r), v in x.items() if d <= day and site[sid].configuration_id == cfg)
        got = sum(q.quantity for q in scenario.inventory if q.configuration_id == cfg and q.available_date <= day)
        model.add(used <= got)
```

## 5. Locks

A locked `PlannedInstall` fixes one variable to 1. If that variable does not exist (crew-day removed, skill mismatch), do not drop the lock. Report `LOCK_CONFLICT` and return `infeasible`.

```python
for a in scenario.current_plan:
    if a.locked:
        key = (a.site_id, a.date, a.crew_id)
        if key not in x:
            conflicts.append(a)
        else:
            model.add(x[key] == 1)
```

## 6. Lexicographic stages with one time budget

Recovery stages (SPEC section 7): late-or-unscheduled count, aggregate delay (unscheduled use `unscheduled_penalty_days`), operating value (maximize), `changed_installs`, travel. Strict stages: value, `changed_installs`, travel.

```python
import time

def solve_stages(model, stages, budget_s, seed, workers):
    deadline = time.monotonic() + budget_s
    metas, prev = [], None
    for name, expr, sense in stages:          # sense in {"min", "max"}
        left = deadline - time.monotonic()
        if left <= 0.05:
            metas.append(StageMeta(name=name, status=StageStatus.skipped, elapsed_ms=0))
            continue
        model.minimize(expr) if sense == "min" else model.maximize(expr)
        if prev is not None:
            model.clear_hints()
            for v in all_vars:
                model.add_hint(v, prev.value(v))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = left
        solver.parameters.random_seed = seed
        solver.parameters.num_workers = workers
        t0 = time.monotonic()
        st = solver.solve(model)
        ms = int((time.monotonic() - t0) * 1000)
        status = STAGE_STATUS[st]
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            val, bnd = solver.objective_value, solver.best_objective_bound
            gap = abs(val - bnd) / max(1.0, abs(val))
            metas.append(StageMeta(name=name, status=status, value=val, bound=bnd, gap=gap, elapsed_ms=ms))
            best = round(val)
            model.add(expr <= best) if sense == "min" else model.add(expr >= best)
            prev = solver
        else:
            metas.append(StageMeta(name=name, status=status, elapsed_ms=ms))
            break                              # later stages: skipped
    return metas, prev
```

Rules:
- One total budget (`time_limit_s` or `config.solve_time_limit_s`). Never an unlimited budget per stage.
- Keep objectives integer. Scale USD to cents before adding value to the model.
- If any stage ends `feasible` (not `optimal`), the plan status is `feasible`. Do not claim a lexicographic optimum.
- Fixing a stage uses `<=` (min) or `>=` (max) on the achieved integer value.
- Remaining stages after a failure are `skipped`.

## 7. Reproducibility

Always set `random_seed = config.random_seed` and `num_workers = config.num_workers`. Tests use `num_workers=1`. Same inputs, same seed, same workers gives the same plan.

## 8. Status mapping

```python
STAGE_STATUS = {
    cp_model.OPTIMAL: StageStatus.optimal,
    cp_model.FEASIBLE: StageStatus.feasible,
    cp_model.INFEASIBLE: StageStatus.infeasible,
    cp_model.UNKNOWN: StageStatus.timeout_no_incumbent,
}
```

- `MODEL_INVALID` is a bug. Raise. Do not map it to a plan status.
- `UNKNOWN` on the first stage means `PlanStatus.timeout_no_incumbent`. It is not `infeasible`.
- Input errors (loader, edits that reference unknown IDs) give `PlanStatus.invalid_input` with `input_issues`.
- Never return assignments with `infeasible` or `timeout_no_incumbent`.

## 9. Hints for minimal change to the current plan

Unlocked installs in `scenario.current_plan` are the starting point. Hint them. Count moves as the `changed_installs` objective, do not forbid them.

```python
for a in scenario.current_plan:
    key = (a.site_id, a.date, a.crew_id)
    if key in x:
        model.add_hint(x[key], 1)
changed_installs = [1 - x[a.site_id, a.date, a.crew_id] if (a.site_id, a.date, a.crew_id) in x
           else 1 for a in scenario.current_plan if not a.locked]
```

## 10. Explaining infeasibility with assumption literals

Guard each soft-able group (a lock, a deadline, a force-include) with a literal. Pass them as assumptions. On `INFEASIBLE`, ask which subset is enough.

```python
lit = {}
for a in locked:
    lit[a.site_id] = model.new_bool_var(f"lock_{a.site_id}")
    model.add(x[a.site_id, a.date, a.crew_id] == 1).only_enforce_if(lit[a.site_id])
model.add_assumptions(list(lit.values()))
solver.parameters.num_workers = 1           # required: core extraction is single-threaded
if solver.solve(model) == cp_model.INFEASIBLE:
    core = solver.sufficient_assumptions_for_infeasibility()   # list of literal indices
    culprits = [sid for sid, l in lit.items() if l.index in core]
```

The core is sufficient, not minimal. Say "these constraints together cannot all hold". Do not claim a single cause. A tight resource is not proof of why a job was deferred (SPEC section 9). Hard reason codes come from data checks only: `NOT_READY`, `SKILL_MISMATCH`, `CLUSTER_NOT_ALLOWED`, `NO_LEGAL_DATE`, `DEADLINE_BEFORE_READY`, `LOCK_CONFLICT`.

## 11. Keep the event loop free

CP-SAT blocks. Run it in a thread.

```python
from fastapi.concurrency import run_in_threadpool

@app.post("/api/plans")
async def create_plan(req: PlanRequest) -> PlanResult:
    return await run_in_threadpool(plan, load_scenario(req.scenario_id), req)
```

`asyncio.to_thread(plan, scenario, req)` also works. Keep the planner callable without FastAPI.

## 12. Tests that prove optimality on tiny cases

- `backend/app/validate/enumerate_tiny.py` (Lane A) brute-forces every assignment: each job is `None` or one legal (crew, day). Apply locks, cluster, capacity, inventory. Compare lexicographic keys.
- The planner's objective must equal the enumerator's for every case in `data/demo/tiny/expected/`.
- Compare objectives, not assignments, unless the optimum is unique (it is unique for the tiny cases).
- Monotonic test: add a crew-day, re-solve, the proven optimal objective is never worse.
- Status tests: zero time budget or a huge instance gives `timeout_no_incumbent`. A lock on a removed crew-day gives `infeasible`.

---

# Battery valuation (HiGHS via scipy.optimize.milp)

For one site and one commissioning date. Operation starts at the first interval after install-day completion plus `qualification_lag_days`. Before that: no charge, no discharge, no value. Horizon ends at `evaluation_end` for every date.

Per interval t = 0..T-1 with length `dt` hours (`interval_hours`):

```text
E[t+1] = E[t] + eta_c * c[t] * dt - d[t] * dt / eta_d
reserve <= E[t] <= capacity
0 <= c[t] <= Pc * m[t]
0 <= d[t] <= Pd * (1 - m[t])          m[t] binary: 1 charge, 0 discharge
E[0] = E[T] = reserve
maximize sum(price[t] / 1000 * (d[t] - c[t]) * dt)     USD, price in USD/MWh
```

Variable layout for `milp` (minimize, so negate): `[c(0..T-1), d(0..T-1), E(0..T), m(0..T-1)]`.

```python
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix

def dispatch(price, dt, b: BatteryConfig, time_limit=30.0):
    T = len(price)
    ic, id_, iE, im = 0, T, 2 * T, 3 * T + 1
    n = 4 * T + 1
    cost = np.zeros(n)
    cost[ic:ic + T] = price / 1000 * dt
    cost[id_:id_ + T] = -price / 1000 * dt

    A = lil_matrix((3 * T, n)); lo = np.zeros(3 * T); hi = np.zeros(3 * T)
    for t in range(T):
        A[t, iE + t + 1] = 1; A[t, iE + t] = -1
        A[t, ic + t] = -b.eta_charge * dt[t]; A[t, id_ + t] = dt[t] / b.eta_discharge
        A[T + t, ic + t] = 1; A[T + t, im + t] = -b.charge_limit_kw
        lo[T + t] = -np.inf
        A[2 * T + t, id_ + t] = 1; A[2 * T + t, im + t] = b.discharge_limit_kw
        lo[2 * T + t] = -np.inf; hi[2 * T + t] = b.discharge_limit_kw

    lb = np.zeros(n); ub = np.full(n, np.inf)
    ub[ic:ic + T] = b.charge_limit_kw; ub[id_:id_ + T] = b.discharge_limit_kw
    lb[iE:iE + T + 1] = b.reserve_kwh; ub[iE:iE + T + 1] = b.capacity_kwh
    lb[iE] = ub[iE] = lb[iE + T] = ub[iE + T] = b.reserve_kwh
    ub[im:im + T] = 1
    integrality = np.zeros(n); integrality[im:im + T] = 1

    res = milp(cost, constraints=LinearConstraint(A.tocsr(), lo, hi),
               bounds=Bounds(lb, ub), integrality=integrality,
               options={"time_limit": time_limit})
    return res   # res.status 0 = optimal. Anything else: record it, never use res.fun as exact.
```

Rules:
- Prices can be negative. Do not assume losses stop cycling. The binary mode prevents simultaneous charge and discharge.
- `dt` comes from `interval_hours` per row. Never assume 0.25.
- One continuous horizon per commissioning date. No daily resets.
- Record `solver_status` on every `ValueTableRow`. A non-optimal solve cannot become an exact objective coefficient.
- Label value as modeled gross operating margin with hindsight prices. Never "profit" or "ROI".
- Cache key: profile, configuration, zone, commissioning timestamp, evaluation end, input hashes.

Required tests (`backend/tests/lane_a/test_battery.py`):
1. Energy conservation: recompute E from c and d. Matches within 1e-6.
2. Power limits: every c and d within limits.
3. No simultaneous cycling: `min(c[t], d[t]) <= 1e-9` for every t.
4. Boundary energy: `E[0] == E[T] == reserve`.
5. Negative prices: with a negative-price block the solver charges there and never discharges into it.
6. Flat prices: value is 0 (losses make any cycling a loss).
7. Identical sites in one zone and one date get identical values.
8. Later commissioning never gets more value when prices are nonnegative over the extra window (sanity, not a law. Skip if prices go negative).
