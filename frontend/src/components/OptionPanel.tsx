import { useEffect, useRef, useState } from "react";
import type { Schema } from "../api/types";
import { money } from "../lib/format";
import {
  hasValidPlan,
  statusLabel,
  unproven,
  validationLabel,
} from "../lib/recovery";

type Option = Schema["RecoveryOption"];

export function OptionPanel({
  option,
  mockLimited,
  approving,
  approval,
  error,
  onApprove,
}: {
  option: Option | undefined;
  mockLimited: boolean;
  approving: boolean;
  approval: Schema["ApproveResult"] | null;
  error: string | null;
  onApprove: (option: Option) => void;
}) {
  const [confirming, setConfirming] = useState<Option | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const approveRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (confirming && !dialog.open) dialog.showModal();
    if (!confirming && dialog.open) dialog.close();
  }, [confirming]);
  if (!option) return null;
  const valid = hasValidPlan(option);
  const canApprove = valid && !mockLimited;
  const closeDialog = () => {
    setConfirming(null);
    approveRef.current?.focus();
  };
  return (
    <section
      className="panel option-panel"
      aria-label="Selected recovery option"
      data-testid="option-panel"
    >
      <div className="panel-heading">
        <h2>Selected option</h2>
        <span className="badge" data-testid="option-panel-status">
          {statusLabel(option)} · {validationLabel(option)}
        </span>
        {option.stub && <span className="badge">Stub data</span>}
      </div>
      <div className="option-panel-body">
        <strong>{option.action_label}</strong>
        <p>{option.diff_vs_original.headline}</p>
        {!valid && (
          <p role="alert" className="error">
            This option has no validated plan. The calendar does not draw it and
            approval is off.
          </p>
        )}
        {valid && unproven(option) && (
          <p className="warning">
            Best found, not proven. The solver stopped before it proved that no
            better plan exists.
          </p>
        )}
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
        {valid && mockLimited && (
          <small>
            This option has no recorded approval response. Use the live API to
            approve it.
          </small>
        )}
        <button
          ref={approveRef}
          type="button"
          className="primary"
          disabled={!canApprove || approving || !!approval}
          onClick={() => setConfirming(option)}
          data-testid="approve-option"
          aria-keyshortcuts="a"
        >
          {approving ? "Approving…" : "Approve"}
        </button>
      </div>
      <dialog
        ref={dialogRef}
        className="approve-dialog"
        aria-labelledby="approve-title"
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
            <h2 id="approve-title">Confirm this recovery</h2>
            <p>
              Approve “{confirming.action_label}” with{" "}
              {confirming.counts.deadlines_missed} deadlines missed and{" "}
              {confirming.counts.customers_to_reschedule} customers to
              reschedule?
            </p>
            <div className="actions">
              <button type="button" onClick={closeDialog}>
                Cancel
              </button>
              <button
                type="button"
                className="primary"
                disabled={approving}
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
