import type { Schema } from "../api/types";
import { money } from "../lib/format";

export function DisruptionBar({
  description,
  result,
  loading,
  error,
}: {
  description: string;
  result: Schema["RecoveryOptionsResult"] | undefined;
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
            <strong>{money(result.no_action.economics.net_impact_usd)}</strong>
            <span>No-action modeled cost</span>
          </div>
        </div>
      )}
    </section>
  );
}
