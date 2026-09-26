import { useState } from "react";
import type { Edit, Scenario } from "../api/types";
import { mockMode } from "../api/client";
import { dateLabel } from "../lib/format";
export function EditControls({
  scenario,
  edits,
  onEdit,
  onReset,
}: {
  scenario: Scenario;
  edits: Edit[];
  onEdit: (edit: Edit) => void;
  onReset: () => void;
}) {
  const [crew, setCrew] = useState(scenario.crew_days[0]?.crew_id ?? "");
  const [date, setDate] = useState(scenario.config.planning_start);
  return (
    <section className="disruptions" aria-label="Disruption controls">
      <div>
        <span className="eyebrow">DISRUPTION</span>
        <strong>
          {edits.length
            ? `${edits.length} change applied`
            : "Test a crew absence"}
        </strong>
      </div>
      <label>
        Crew{" "}
        <select
          value={crew}
          disabled={mockMode}
          onChange={(e) => setCrew(e.target.value)}
        >
          {[...new Set(scenario.crew_days.map((c) => c.crew_id))].map((c) => (
            <option key={c} value={c}>
              Crew {c}
            </option>
          ))}
        </select>
      </label>
      <label>
        Day{" "}
        <input
          aria-label="Crew absence date"
          type="date"
          value={date}
          disabled={mockMode}
          onChange={(e) => setDate(e.target.value)}
        />
      </label>
      <button
        disabled={edits.some(
          (e) =>
            e.kind === "remove_crew_day" &&
            e.crew_id === crew &&
            e.date === date,
        )}
        onClick={() => onEdit({ kind: "remove_crew_day", crew_id: crew, date })}
      >
        Remove crew-day
      </button>
      <button onClick={onReset}>Reset demo</button>
      <span className="muted">
        {mockMode
          ? `Recorded: Crew A out ${dateLabel(scenario.config.planning_start)}`
          : "Changes apply only to this analysis."}
      </span>
    </section>
  );
}
