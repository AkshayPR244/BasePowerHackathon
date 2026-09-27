import type { Narrative } from "../narratives";
export function ScenarioBriefing({
  report,
  primaryActive,
  onApply,
  disabled,
  hasDisruption,
  activeCopy,
}: {
  report: Narrative | undefined;
  primaryActive: boolean;
  onApply: () => void;
  disabled: boolean;
  hasDisruption: boolean;
  activeCopy?: {
    trigger: string;
    whatWentWrong: string;
    unavailableResources: string[];
    question: string;
  };
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
          <p>
            {primaryActive
              ? (activeCopy?.trigger ?? report.trigger)
              : report.situation}
          </p>
          <div className="briefing-incident" aria-label="Operational impact">
            <div>
              <span className="eyebrow">What went wrong</span>
              <strong>
                {primaryActive
                  ? (activeCopy?.whatWentWrong ?? report.what_went_wrong)
                  : "Nothing yet — this is the healthy starting plan."}
              </strong>
            </div>
            <div>
              <span className="eyebrow">
                Unavailable or constrained resources
              </span>
              {primaryActive ? (
                <ul>
                  {(
                    activeCopy?.unavailableResources ??
                    report.unavailable_resources
                  ).map((resource) => (
                    <li key={resource}>{resource}</li>
                  ))}
                </ul>
              ) : (
                <strong>
                  None. All planned crews, inventory, and customer windows are
                  available.
                </strong>
              )}
            </div>
          </div>
          {primaryActive && (
            <p>
              <strong>{activeCopy?.question ?? report.question}</strong>
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
