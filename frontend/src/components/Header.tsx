import type { Plan, Scenario, Schema } from "../api/types";
import { mockMode } from "../api/client";
import { dateLabel } from "../lib/format";
const labels: Record<Schema["PlanStatus"], string> = {
  optimal: "Optimal",
  feasible: "Feasible",
  infeasible: "Infeasible",
  timeout_no_incumbent: "Timed out (no plan found)",
  invalid_input: "Invalid input",
};
export function Validation({ plan }: { plan: Plan }) {
  return (
    <span
      className={`badge ${!plan.validation.checked || !plan.validation.valid ? "warning" : ""}`}
    >
      {!plan.validation.checked
        ? "Not validated"
        : plan.validation.valid
          ? "Validated"
          : `${plan.validation.issues.length} violations`}
    </span>
  );
}
export function Header({
  scenario,
  plan,
  scenarios,
  onScenario,
  theme,
  onTheme,
}: {
  scenario: Scenario;
  plan: Plan | null;
  scenarios: Schema["ScenarioSummary"][];
  onScenario: (id: string) => void;
  theme: string;
  onTheme: () => void;
}) {
  const gap = plan?.stages.reduce((n, s) => Math.max(n, s.gap ?? 0), 0) ?? 0;
  return (
    <header>
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          R/
        </span>
        <div>
          <h1>Rollout Planner</h1>
          <span className="eyebrow">OPERATIONS / RECOVERY WORKSPACE</span>
        </div>
      </div>
      <div className="header-controls">
        <span className="badge">{mockMode ? "Recorded demo" : "Live API"}</span>
        <button onClick={onTheme} aria-label="Toggle dark mode">
          {theme === "dark" ? "Light" : "Dark"}
        </button>
      </div>
      <div className="context">
        <label>
          Scenario{" "}
          <select
            value={scenario.scenario_id}
            onChange={(e) => onScenario(e.target.value)}
          >
            {scenarios.map((s) => (
              <option key={s.scenario_id} value={s.scenario_id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <span className="badge">
          {scenario.config.synthetic ? "Synthetic data" : "Mixed-source data"}
        </span>
        <span className="mono">
          {dateLabel(scenario.config.planning_start)} —{" "}
          {dateLabel(scenario.config.planning_end)}
        </span>
        <span>{scenario.config.timezone}</span>
        <span className="policy">
          Policy:{" "}
          {plan?.objective_policy.replaceAll("_", " ") ??
            scenario.config.objective_policy.replaceAll("_", " ")}
        </span>
        {plan && (
          <>
            <strong>
              {labels[plan.status]}
              {plan.status === "feasible"
                ? ` (gap ${(gap * 100).toFixed(1)}%)`
                : ""}
            </strong>
            <Validation plan={plan} />
          </>
        )}
      </div>
    </header>
  );
}
