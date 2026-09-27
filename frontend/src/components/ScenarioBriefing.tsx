import type { Narrative } from "../narratives";
export function ScenarioBriefing({
  report,
  primaryActive,
  onApply,
  disabled,
  hasDisruption,
}: {
  report: Narrative | undefined;
  primaryActive: boolean;
  onApply: () => void;
  disabled: boolean;
  hasDisruption: boolean;
}) {
  if (!report) return null;
  return (
    <section className="scenario-briefing" aria-label="Scenario briefing">
      <details open>
        <summary>
          <span className="eyebrow">Scenario briefing · {report.operator}</span>
          <strong>{report.title}</strong>
        </summary>
        <div className="briefing-body">
          <p>{primaryActive ? report.trigger : report.situation}</p>
          {primaryActive && (
            <p>
              <strong>{report.question}</strong>
            </p>
          )}
          {!primaryActive && (
            <button className="primary" disabled={disabled} onClick={onApply}>
              {hasDisruption
                ? "Apply primary disruption"
                : "Analyze healthy baseline"}
            </button>
          )}
        </div>
      </details>
      <p className="briefing-truth">{report.truth_label}</p>
    </section>
  );
}
