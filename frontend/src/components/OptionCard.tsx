import type { Schema } from "../api/types";
import { money } from "../lib/format";

export function OptionCard({
  option,
  selected,
  shortcut,
  onSelect,
}: {
  option: Schema["RecoveryOption"];
  selected: boolean;
  shortcut: string;
  onSelect: (optionId: string) => void;
}) {
  if (
    !["optimal", "feasible"].includes(option.status) ||
    !option.result.validation.valid
  ) {
    return (
      <section className="panel" aria-label="Unavailable recovery option">
        <strong>{option.action_label}</strong>
        <p role="status">
          {option.status === "infeasible" ? "Infeasible" : "No validated plan"}
        </p>
        <p>{option.result.message}</p>
        <p>
          Costs and deadline outcomes are not evaluated without a feasible plan.
        </p>
        <button disabled>Approve unavailable</button>
      </section>
    );
  }
  const crews = [
    ...new Set(option.crew_load.map((load) => load.crew_id)),
  ].sort();
  return (
    <button
      type="button"
      className={`option-card ${selected ? "selected" : ""}`}
      aria-pressed={selected}
      aria-keyshortcuts={shortcut}
      data-testid={`option-${option.option_id}`}
      data-option-kind={option.kind}
      onClick={() => onSelect(option.option_id)}
    >
      <span className="option-label">
        <strong>{option.action_label}</strong>
        {option.lowest_modeled_cost && (
          <span className="badge">Lowest modeled cost</span>
        )}
        {option.stub && <span className="badge">Stub data</span>}
      </span>
      <span className="option-numbers">
        <span>
          <strong>{money(option.economics.net_impact_usd)}</strong>
          <small>Modeled cost</small>
        </span>
        <span>
          <strong>{money(option.economics.advantage_vs_no_action_usd)}</strong>
          <small>Advantage vs no action</small>
        </span>
      </span>
      <span className="option-details">
        {option.counts.deadlines_missed} deadlines missed ·{" "}
        {option.counts.customers_to_reschedule} customers to reschedule
        {option.overtime_min > 0 && ` · ${option.overtime_min} min overtime`}
      </span>
      <span className="mini-lanes" aria-label="Crew load before and after">
        {crews.map((crew) => (
          <span className="mini-lane" key={crew}>
            <span className="mini-lane-label">{crew}</span>
            <span className="mini-lane-days">
              {option.crew_load
                .filter((load) => load.crew_id === crew)
                .map((load) => (
                  <span
                    className="mini-lane-day"
                    key={`${crew}-${load.date}`}
                    title={`${crew} ${load.date}: ${(load.before * 100).toFixed(0)}% before, ${(load.after * 100).toFixed(0)}% after`}
                  >
                    <span
                      className="mini-before"
                      style={{ height: `${load.before * 100}%` }}
                    />
                    <span
                      className="mini-after"
                      style={{ height: `${load.after * 100}%` }}
                    />
                  </span>
                ))}
            </span>
          </span>
        ))}
      </span>
    </button>
  );
}
