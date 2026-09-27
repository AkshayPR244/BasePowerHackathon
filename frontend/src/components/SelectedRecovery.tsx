import { useEffect, useRef, useState } from "react";
import type { Schema } from "../api/types";
import { statusLabel, unproven } from "../lib/recovery";

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
  onApprove: (option: RecoveryOption) => void;
}) {
  const [confirming, setConfirming] = useState<RecoveryOption | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const approveRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (confirming && !dialog.open) dialog.showModal();
    if (!confirming && dialog.open) dialog.close();
  }, [confirming]);
  const closeDialog = () => {
    setConfirming(null);
    approveRef.current?.focus();
  };
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
  const confirmLabel =
    confirming?.option_id === option.option_id
      ? actionLabel
      : confirming?.action_label;
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
          {valid && unproven(option) && (
            <span className="stale-result-note" data-testid="unproven-note">
              {statusLabel(option)}. The solver stopped before it proved that no
              better plan exists.
            </span>
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
          ref={approveRef}
          type="button"
          className="approve-button"
          disabled={!valid || busy || !!approval}
          onClick={() => setConfirming(option)}
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
      <dialog
        ref={dialogRef}
        className="confirm-dialog"
        aria-labelledby="confirm-heading"
        data-testid="approve-dialog"
        onCancel={(event) => {
          event.preventDefault();
          closeDialog();
        }}
        onKeyDown={(event) => {
          if (event.key !== "Tab") return;
          // Keep Tab inside the dialog instead of moving to the browser UI.
          const focusable = [
            ...event.currentTarget.querySelectorAll<HTMLElement>(
              "button:not(:disabled)",
            ),
          ];
          if (!focusable.length) return;
          const index = focusable.indexOf(
            document.activeElement as HTMLElement,
          );
          const next = event.shiftKey
            ? (index - 1 + focusable.length) % focusable.length
            : (index + 1) % focusable.length;
          event.preventDefault();
          focusable[next].focus();
        }}
      >
        {confirming && (
          <>
            <h2 id="confirm-heading">Approve this recovery?</h2>
            <p>
              {confirmLabel}. {confirming.counts.deadlines_missed} deadlines
              missed. {confirming.counts.customers_to_reschedule} customers to
              reschedule.
            </p>
            {confirming.diff_vs_original.changes
              .slice(0, 2)
              .map((change, index) => (
                <p key={change.job_id ?? `${change.site_id}-${index}`}>
                  {change.note}
                </p>
              ))}
            <div className="confirm-actions">
              <button type="button" onClick={closeDialog}>
                Keep reviewing
              </button>
              <button
                type="button"
                className="approve-button"
                disabled={busy}
                onClick={() => {
                  const frozen = confirming;
                  closeDialog();
                  onApprove(frozen);
                }}
              >
                Confirm approval
              </button>
            </div>
          </>
        )}
      </dialog>
    </section>
  );
}
