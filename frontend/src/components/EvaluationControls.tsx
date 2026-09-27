import { useState } from "react";
import type { Scenario, Schema } from "../api/types";
import { dateLabel } from "../lib/format";
import {
  earliestDate,
  statusLabel,
  validationLabel,
  type Disruption,
  type Intervention,
} from "../lib/recovery";

export function EvaluationControls({
  scenario,
  disruption,
  option,
  onEvaluate,
  pending,
  result,
  error,
}: {
  scenario: Scenario;
  disruption: Disruption[];
  option: Schema["RecoveryOption"] | undefined;
  onEvaluate: (disruption: Disruption[], interventions: Intervention[]) => void;
  pending: boolean;
  result: Schema["RecoveryOption"] | null;
  error: string | null;
}) {
  const firstOpen = earliestDate(disruption) ?? scenario.config.planning_start;
  const lastDay = scenario.config.planning_end;
  const workDays = [...new Set(scenario.crew_days.map((c) => c.date))]
    .filter((day) => day >= firstOpen && day <= lastDay)
    .sort();
  const crews = [...new Set(scenario.crew_days.map((c) => c.crew_id))].sort(
    (left, right) => {
      const rank = (crew: string) =>
        scenario.crew_days.some(
          (c) => c.crew_id === crew && c.skills.includes("install"),
        )
          ? 0
          : 1;
      return rank(left) - rank(right) || left.localeCompare(right);
    },
  );
  const [crew, setCrew] = useState(crews[0] ?? "");
  const [date, setDate] = useState(
    workDays.find((day) => day > firstOpen) ?? firstOpen,
  );
  const visits = (option?.result.assignments ?? [])
    .filter((a) => a.date >= firstOpen && a.job_id)
    .map((a) => a.job_id!)
    .sort();
  const [pickedVisit, setVisit] = useState("");
  const skillOf = new Map(
    scenario.sites.flatMap((s) =>
      (s.visits ?? []).map((v) => [v.job_id, v.required_skill] as const),
    ),
  );
  const crewSkills = new Set(
    scenario.crew_days
      .filter((c) => c.crew_id === crew)
      .flatMap((c) => c.skills),
  );
  // The server rejects a move to a crew without the visit's skill.
  const movable = visits.filter((v) => crewSkills.has(skillOf.get(v) ?? ""));
  const visit = visits.includes(pickedVisit) ? pickedVisit : (visits[0] ?? "");
  const moveVisit = movable.includes(visit) ? visit : (movable[0] ?? "");
  const dateValid = !!date && date >= firstOpen && date <= lastDay;
  const disabled = pending || !crew || !dateValid;
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
      <div className="evaluation-inputs">
        <label>
          Crew
          <select value={crew} onChange={(e) => setCrew(e.target.value)}>
            {crews.map((c) => (
              <option key={c} value={c}>
                Crew {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          Day
          <input
            type="date"
            aria-label="Change day"
            value={date}
            min={firstOpen}
            max={lastDay}
            aria-invalid={!dateValid}
            onChange={(e) => setDate(e.target.value)}
          />
        </label>
        <label>
          Visit
          <select
            value={visit}
            disabled={!visits.length}
            onChange={(e) => setVisit(e.target.value)}
          >
            {visits.map((jobId) => (
              <option key={jobId} value={jobId}>
                {jobId}
              </option>
            ))}
          </select>
        </label>
      </div>
      {!dateValid && (
        <p className="error padded-x" role="alert">
          Pick a day from {dateLabel(firstOpen)} to {dateLabel(lastDay)}.
          Earlier days are frozen.
        </p>
      )}
      <div className="evaluation-actions">
        <button
          type="button"
          disabled={disabled}
          data-testid="knockout-crew-day"
          aria-keyshortcuts="k"
          onClick={() =>
            onEvaluate(
              [...disruption, { kind: "remove_crew_day", crew_id: crew, date }],
              [],
            )
          }
        >
          Knock out Crew {crew} · {dateValid ? dateLabel(date) : "—"}
        </button>
        <button
          type="button"
          disabled={disabled}
          data-testid="overtime-crew-day"
          onClick={() =>
            onEvaluate(disruption, [
              { kind: "extend_crew_day", crew_id: crew, date, extra_min: 120 },
            ])
          }
        >
          Add 120 min overtime
        </button>
        <button
          type="button"
          disabled={pending || !visit}
          data-testid="pin-visit"
          onClick={() =>
            onEvaluate(disruption, [{ kind: "pin_visit", job_id: visit }])
          }
        >
          Pin {visit || "visit"}
        </button>
        <button
          type="button"
          disabled={disabled || !moveVisit}
          data-testid="move-visit"
          onClick={() =>
            onEvaluate(disruption, [
              { kind: "move_visit", job_id: moveVisit, crew_id: crew, date },
            ])
          }
        >
          Move {moveVisit || "visit"} to Crew {crew}
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
              <small>
                {statusLabel(result)} · {validationLabel(result)}
              </small>
              <p>{result.result.message}</p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
