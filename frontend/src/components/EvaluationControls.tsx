import type { Schema } from "../api/types";

type Edit = Schema["EvaluateRequest"]["interventions"][number];
type Disruption = Schema["EvaluateRequest"]["disruption"][number];

export function EvaluationControls({
  onEvaluate,
  pending,
  result,
  error,
}: {
  onEvaluate: (disruption: Disruption[], interventions: Edit[]) => void;
  pending: boolean;
  result: Schema["RecoveryOption"] | null;
  error: string | null;
}) {
  const outage: Disruption[] = [
    { kind: "remove_crew_day", crew_id: "IB", date: "2018-06-13" },
  ];
  const overtime: Edit[] = [
    {
      kind: "extend_crew_day",
      crew_id: "BA",
      date: "2018-06-15",
      extra_min: 120,
    },
  ];
  const pin: Edit[] = [{ kind: "pin_visit", job_id: "N-02-B" }];
  const move: Edit[] = [
    { kind: "move_visit", job_id: "N-02-B", crew_id: "BA", date: "2018-06-12" },
  ];
  const base: Disruption[] = [
    { kind: "remove_crew_day", crew_id: "IA", date: "2018-06-14" },
    { kind: "remove_crew_day", crew_id: "IB", date: "2018-06-14" },
    { kind: "remove_crew_day", crew_id: "BA", date: "2018-06-14" },
  ];
  const run = (extra: Disruption[], interventions: Edit[]) =>
    onEvaluate([...base, ...extra], interventions);

  return (
    <section
      className="panel evaluation-controls"
      aria-label="Test a recovery change"
      data-testid="evaluation-controls"
    >
      <div className="panel-heading">
        <h2>Test a change</h2>
        <span>Evaluate without replacing the selected option</span>
      </div>
      <div className="evaluation-actions">
        <button
          type="button"
          disabled={pending}
          data-testid="knockout-crew-day"
          aria-keyshortcuts="k"
          onClick={() => run(outage, [])}
        >
          Knock out Crew IB · Wed 13 Jun
        </button>
        <button
          type="button"
          disabled={pending}
          onClick={() => run([], overtime)}
        >
          Add 120 min overtime
        </button>
        <button type="button" disabled={pending} onClick={() => run([], pin)}>
          Pin N-02 battery day
        </button>
        <button type="button" disabled={pending} onClick={() => run([], move)}>
          Move N-02 battery day
        </button>
      </div>
      {pending && <p role="status">Solving recovery change…</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {result && (
        <div className="evaluation-result" role="status">
          {result.stub ? (
            <p>
              Stub data. The evaluator returned a fixture and did not calculate
              this change.
            </p>
          ) : (
            <>
              <strong>{result.action_label}</strong>
              <p>{result.result.message}</p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
