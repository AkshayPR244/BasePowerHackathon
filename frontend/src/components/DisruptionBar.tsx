import type { Schema } from "../api/types";
import { adjustedCostClass, money } from "../lib/format";

export function DisruptionBar({
  description,
  result,
  loading,
  error,
  truthLabel,
}: {
  description: string;
  result: Schema["RecoveryOptionsResult"] | undefined;
  truthLabel?: string;
  loading: boolean;
  error: string | null;
}) {
  return (
    <section
      className="disruptions disruption-bar"
      aria-label="Disruption impact"
      data-testid="disruption-bar"
    >
      <div className="disruption-summary">
        <span className="eyebrow">Disruption analyzed</span>
        <strong data-testid="disruption-description">{description}</strong>
        {result ? (
          <p data-testid="impact-headline">{result.impact.headline}</p>
        ) : loading ? (
          <p role="status">Calculating the impact on the current plan…</p>
        ) : (
          <p role="alert" className="error">
            {error ?? "Disruption impact is unavailable."}
          </p>
        )}
        {truthLabel && <small>{truthLabel}</small>}
      </div>
      {result?.stub && <span className="badge">Stub data</span>}
      {result && (
        <div className="disruption-metrics">
          <div data-testid="affected-visits">
            <strong>{result.impact.affected_job_ids.length}</strong>
            <span>Visits affected</span>
          </div>
          <div data-testid="deadlines-at-risk">
            <strong>{result.impact.deadlines_at_risk}</strong>
            <span>Deadlines at risk</span>
          </div>
          <div data-testid="no-action-cost">
            <strong
              className={adjustedCostClass(
                result.no_action.economics.net_impact_usd,
              )}
            >
              {money(result.no_action.economics.net_impact_usd)}
            </strong>
            <span>No-action adjusted cost</span>
          </div>
        </div>
      )}
    </section>
  );
}
