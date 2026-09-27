import { useState } from "react";
import type { Schema } from "../api/types";
import { money } from "../lib/format";

export function OptionPanel({
  option,
  canApprove,
  approving,
  approval,
  error,
  onApprove,
}: {
  option: Schema["RecoveryOption"] | undefined;
  canApprove: boolean;
  approving: boolean;
  approval: Schema["ApproveResult"] | null;
  error: string | null;
  onApprove: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  if (!option) return null;
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
  return (
    <section
      className="panel option-panel"
      aria-label="Selected recovery option"
      data-testid="option-panel"
    >
      <div className="panel-heading">
        <h2>Selected option</h2>
        {option.stub && <span className="badge">Stub data</span>}
      </div>
      <div className="option-panel-body">
        <strong>{option.action_label}</strong>
        <p>{option.diff_vs_original.headline}</p>
        <div className="pinned-metrics">
          <div>
            <span className="eyebrow">Modeled cost</span>
            <strong>{money(option.economics.net_impact_usd)}</strong>
          </div>
          <div>
            <span className="eyebrow">Deadlines missed</span>
            <strong>{option.counts.deadlines_missed}</strong>
          </div>
          <div>
            <span className="eyebrow">Customers to reschedule</span>
            <strong>{option.counts.customers_to_reschedule}</strong>
          </div>
        </div>
        <details>
          <summary>
            Review changes ({option.diff_vs_original.changes.length})
          </summary>
          <ul>
            {option.diff_vs_original.changes.map((change, index) => (
              <li key={change.job_id ?? `${change.site_id}-${index}`}>
                <strong className="mono">{change.site_id}</strong>
                <span>{change.note}</span>
              </li>
            ))}
          </ul>
        </details>
        <details data-testid="economic-breakdown">
          <summary>
            Modeled cost breakdown ({option.economics.lines.length})
          </summary>
          <ul>
            {option.economics.lines.map((line, index) => (
              <li key={`${line.label}-${index}`}>
                <strong>{line.label}</strong>
                <span>{money(line.amount_usd)}</span>
                <small>{line.basis}</small>
              </li>
            ))}
          </ul>
        </details>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {approval && (
          <p role="status" data-testid="approval-result">
            {approval.summary} {approval.stub && "Stub data."}
          </p>
        )}
        {!canApprove && (
          <small>
            This option has no recorded approval response. Use the live API to
            approve it.
          </small>
        )}
        <button
          type="button"
          className="primary"
          disabled={!canApprove || approving || !!approval}
          onClick={() => setConfirming(true)}
          data-testid="approve-option"
          aria-keyshortcuts="a"
        >
          Approve
        </button>
      </div>
      {confirming && (
        <div className="dialog-backdrop">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="approve-title"
            className="approve-dialog"
          >
            <h2 id="approve-title">Confirm this recovery</h2>
            <p>
              Approve “{option.action_label}” with{" "}
              {option.counts.deadlines_missed} deadlines missed and{" "}
              {option.counts.customers_to_reschedule} customers to reschedule?
            </p>
            <div className="actions">
              <button type="button" onClick={() => setConfirming(false)}>
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                disabled={approving}
                onClick={() => {
                  setConfirming(false);
                  onApprove();
                }}
              >
                Confirm approval
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
