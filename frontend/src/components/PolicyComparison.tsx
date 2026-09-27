import { useState } from "react";
import { api, unwrap, mockMode } from "../api/client";
import type { Edit, Plan } from "../api/types";
import { money } from "../lib/format";
export function PolicyComparison({
  scenarioId,
  revision,
  edits,
}: {
  scenarioId: string;
  revision: number;
  edits: Edit[];
}) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function run() {
    setPending(true);
    setPlans([]);
    setError("");
    try {
      const results: Plan[] = [];
      for (const policy of ["value_aware", "deadline_travel_only"] as const) {
        results.push(
          unwrap(
            await api.POST("/api/plans", {
              body: {
                algorithm: "cpsat",
                scenario_id: scenarioId,
                revision,
                mode: "strict",
                edits,
                objective_policy: policy,
              },
            }),
          ),
        );
      }
      setPlans(results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Comparison failed.");
    } finally {
      setPending(false);
    }
  }
  const dates = (p: Plan) =>
    new Map(p.assignments.map((a) => [a.job_id, `${a.crew_id}/${a.date}`]));
  const changed =
    plans.length === 2
      ? plans[1].assignments.filter(
          (a) => dates(plans[0]).get(a.job_id) !== `${a.crew_id}/${a.date}`,
        ).length
      : 0;
  return (
    <section
      className="panel scenario-watch"
      aria-label="Objective policy comparison"
    >
      <strong>Compare objectives under identical constraints</strong>
      <p>
        Apply the primary disruption first. Both strict solves use the same
        homes, locks, resources and edits; only the objective policy changes.
      </p>
      <button
        disabled={mockMode || pending || !edits.length}
        onClick={() => void run()}
      >
        Compare objective policies
      </button>
      {pending && <p role="status">Solving both objective policies…</p>}
      {error && <p role="alert">{error}</p>}
      {plans.map((p) => (
        <p key={p.objective_policy}>
          {p.objective_policy}: {p.status} ·{" "}
          {p.validation.checked
            ? p.validation.valid
              ? "Validator checked"
              : `Validator found ${p.validation.issues.length} ${p.validation.issues.length === 1 ? "violation" : "violations"}`
            : "Validator not run"}{" "}
          ·{" "}
          {p.objective
            ? money(p.objective.operating_value_usd) +
              " modeled operating margin"
            : "No incumbent"}
        </p>
      ))}
      {plans.length === 2 && (
        <p>
          {changed} visit assignments differ. Historical-price hindsight
          benchmark, not forecast profit.
        </p>
      )}
    </section>
  );
}
