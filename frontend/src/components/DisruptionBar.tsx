import type { Schema } from "../api/types";
import { money } from "../lib/format";

export function DisruptionBar({
  result,
  loading,
  error,
  truthLabel,
}: {
  result: Schema["RecoveryOptionsResult"] | undefined;
  truthLabel?: string;
  loading: boolean;
  error: string | null;
}) {
  if (!result)
    return (
      <section
        className="disruptions disruption-bar"
        aria-label="Disruption impact"
        data-testid="disruption-bar"
      >
        {loading ? (
          <p role="status">Loading disruption impact…</p>
        ) : (
          <p role="alert">{error ?? "Disruption impact is unavailable."}</p>
        )}
      </section>
    );

  return (
    <section
      className="disruptions disruption-bar"
      aria-label="Disruption impact"
      data-testid="disruption-bar"
    >
      <div className="disruption-summary">
        <span className="eyebrow">Modeled impact</span>
        <strong>{result.impact.headline}</strong>
        <small>
          {truthLabel ??
            "This replay applies a modeled operational disruption to a real historical storm."}
        </small>
      </div>
      {result.stub && <span className="badge">Stub data</span>}
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
    </section>
  );
}
