import { useState } from "react";
import type { Schema } from "../api/types";

type RecoveryOption = Schema["RecoveryOption"];

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function validationLine(option: RecoveryOption) {
  const report = option.result.validation;
  if (!report.checked)
    return "Validation has not run. This plan is not selectable.";
  if (report.valid)
    return `Checked by ${report.validator}. Constraints passed.`;
  return `Validation failed: ${report.issues.map((issue) => issue.message).join("; ")}`;
}

export function SelectedRecovery({
  option,
  labelOverride,
  stale = false,
  busy,
  approval,
  error,
  onApprove,
}: {
  option: RecoveryOption | undefined;
  labelOverride?: string;
  stale?: boolean;
  busy: boolean;
  approval: Schema["ApproveResult"] | null;
  error: string | null;
  onApprove: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  if (!option) {
    return (
      <section className="selected-recovery" aria-label="Selected recovery">
        <p className="figure-empty">
          No feasible, validated plan can be shown for this trigger.
        </p>
      </section>
    );
  }

  const valid =
    (option.status === "feasible" || option.status === "optimal") &&
    option.result.validation.checked &&
    option.result.validation.valid &&
    !option.stub;
  const changes = option.diff_vs_original.changes;
  const preview = changes.slice(0, 3);
  const actionLabel = labelOverride ?? option.action_label;
  const comparison =
    option.diff_vs_no_action?.headline ??
    "This is the no-action reference plan.";

  return (
    <section
      className="selected-recovery"
      aria-label="Selected recovery"
      data-testid="selected-recovery"
    >
      <div className="selected-summary">
        <div className="selected-copy">
          <span className="selected-action">{actionLabel}</span>
          {stale && (
            <span className="stale-result-note">
              Previous result. Approval is paused until this change is checked.
            </span>
          )}
          <p>{comparison}</p>
          {option.stub && (
            <span className="response-note">Fixture response</span>
          )}
        </div>
        <div className="selected-values">
          <span>
            <strong
              className={
                option.counts.deadlines_missed > 0 ? "promise-risk" : ""
              }
            >
              {option.counts.deadlines_missed}
            </strong>
            <small>Deadlines missed</small>
          </span>
          <span>
            <strong>{option.counts.customers_to_reschedule}</strong>
            <small>Customers to reschedule</small>
          </span>
          <span>
            <strong>{option.counts.visits_moved}</strong>
            <small>Visits moved</small>
          </span>
          <span>
            <strong>{currency.format(option.economics.net_impact_usd)}</strong>
            <small>Modeled cost</small>
          </span>
        </div>
        <button
          type="button"
          className="approve-button"
          disabled={!valid || busy || !!approval}
          onClick={() => setConfirming(true)}
          data-testid="approve-option"
        >
          Approve this recovery
        </button>
      </div>
      <div className="selected-foot">
        <p
          className={
            option.result.validation.valid
              ? "validation-ok"
              : "validation-failed"
          }
          data-testid="validation-line"
        >
          {validationLine(option)}
        </p>
        <div className="change-preview" aria-label="First plan changes">
          {preview.length ? (
            preview.map((change, index) => (
              <p key={change.job_id ?? `${change.site_id}-${index}`}>
                <strong>{change.site_id}</strong> {change.note}
              </p>
            ))
          ) : (
            <p>No visit changes against the current plan.</p>
          )}
          {changes.length > preview.length && (
            <small>{changes.length - preview.length} more changes</small>
          )}
        </div>
      </div>
      {error && (
        <p role="alert" className="request-error">
          {error}
        </p>
      )}
      {approval && (
        <p
          role="status"
          className="approval-status"
          data-testid="approval-status"
        >
          {approval.summary}
        </p>
      )}
      {confirming && (
        <div className="confirm-backdrop">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-heading"
            className="confirm-dialog"
          >
            <h2 id="confirm-heading">Approve this recovery?</h2>
            <p>
              {actionLabel}. {option.counts.deadlines_missed} deadlines missed;{" "}
              {option.counts.customers_to_reschedule} customers to reschedule.
            </p>
            {preview.slice(0, 2).map((change, index) => (
              <p key={change.job_id ?? `${change.site_id}-${index}`}>
                {change.note}
              </p>
            ))}
            <div className="confirm-actions">
              <button type="button" onClick={() => setConfirming(false)}>
                Keep reviewing
              </button>
              <button
                type="button"
                className="approve-button"
                disabled={busy}
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
