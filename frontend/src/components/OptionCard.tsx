import type { Schema } from "../api/types";
import { money } from "../lib/format";
import {
  hasValidPlan,
  statusLabel,
  unproven,
  validationLabel,
} from "../lib/recovery";

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
  const crews = [
    ...new Set(option.crew_load.map((load) => load.crew_id)),
  ].sort();
  const valid = hasValidPlan(option);
  return (
    <button
      type="button"
      className={`option-card ${selected ? "selected" : ""} ${valid ? "" : "invalid"}`}
      aria-pressed={selected}
      aria-keyshortcuts={shortcut}
      data-testid={`option-${option.option_id}`}
      data-option-kind={option.kind}
      onClick={() => onSelect(option.option_id)}
    >
      <span className="option-label">
        <strong>{option.action_label}</strong>
        <span className="option-badges">
          {option.lowest_modeled_cost && (
            <span className="badge">Lowest modeled cost</span>
          )}
          <span
            className={`badge ${valid && !unproven(option) ? "" : "warning"}`}
            data-testid="option-status"
          >
            {statusLabel(option)} · {validationLabel(option)}
          </span>
          {option.stub && <span className="badge">Stub data</span>}
        </span>
      </span>
      {valid ? (
        <span className="option-numbers">
          <span data-testid="option-cost">
            <strong>{money(option.economics.net_impact_usd)}</strong>
            <small>Modeled cost</small>
          </span>
          <span>
            <strong>
              {money(option.economics.advantage_vs_no_action_usd)}
            </strong>
            <small>Advantage vs no action</small>
          </span>
          <span data-testid="option-deadlines">
            <strong>{option.counts.deadlines_missed}</strong>
            <small>Deadlines missed</small>
          </span>
          <span data-testid="option-customers">
            <strong>{option.counts.customers_to_reschedule}</strong>
            <small>Customers to reschedule</small>
          </span>
        </span>
      ) : (
        <span className="option-numbers" data-testid="option-not-evaluated">
          Costs and deadline outcomes are not evaluated without a validated
          plan.
        </span>
      )}
      <span className="option-details">
        {option.overtime_min > 0
          ? `${option.overtime_min} min overtime`
          : "No overtime"}
        {!valid && " · No validated plan to approve"}
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
