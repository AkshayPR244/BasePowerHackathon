import type { Plan, Scenario, Schema } from "../api/types";
import { Status } from "../design/status";
import { dateLabel } from "../lib/format";
import { Validation } from "./Header";
import { temporaryCrewId } from "../lib/recovery";
export function Inspector({
  scenario,
  plan,
  selected,
  onIntervention,
  cf,
  busy,
  canIntervene,
}: {
  scenario: Scenario;
  plan: Plan | null;
  selected: string | null;
  onIntervention: (kind: "force" | "crew") => void;
  cf: Schema["CounterfactualResult"] | null;
  busy: boolean;
  canIntervene: boolean;
}) {
  const site = scenario.sites.find((s) => s.site_id === selected),
    assigned = plan?.assignments.find((a) => a.site_id === selected),
    deferred = plan?.unscheduled.find((u) => u.site_id === selected);
  return (
    <aside className="panel inspector">
      <div className="panel-heading">
        <h2>Site inspector</h2>
        <span>{selected ?? "Select a site"}</span>
      </div>
      {!site ? (
        <p className="padded empty">
          Select an install in the calendar, map, or deferred list to inspect
          its requirements.
        </p>
      ) : (
        <div className="padded">
          <div className="site-title">
            <h2 className="mono">{site.site_id}</h2>
            {(assigned || deferred) && (
              <Status
                state={(assigned ?? deferred)!.state}
                days={assigned?.days_late}
              />
            )}
          </div>
          <p>
            Cluster {site.cluster_id} · {site.load_zone}
          </p>
          <dl>
            <dt>Ready</dt>
            <dd>{dateLabel(site.ready_date)}</dd>
            <dt>Commitment</dt>
            <dd>{dateLabel(site.deadline)}</dd>
            <dt>On-site work</dt>
            <dd>{site.duration_min} min</dd>
            <dt>Required skill</dt>
            <dd>{site.required_skill}</dd>
            <dt>Battery</dt>
            <dd>{site.configuration_id}</dd>
            {assigned && (
              <>
                <dt>Proposed install</dt>
                <dd>
                  Crew {assigned.crew_id} · {dateLabel(assigned.date)}
                </dd>
              </>
            )}
          </dl>
          {deferred && (
            <div className="reason">
              <strong>{deferred.reasons.join(" · ")}</strong>
              <p>{deferred.detail}</p>
            </div>
          )}
          {assigned?.days_late ? (
            <p className="reason">
              This install misses its commitment by {assigned.days_late} day(s).
            </p>
          ) : null}
          <h3>Test an intervention</h3>
          <p className="muted">
            Explore an alternative without replacing the recovery plan.
          </p>
          <div className="stack">
            <button
              disabled={!canIntervene || busy}
              onClick={() => onIntervention("force")}
            >
              Require {site.site_id} by deadline
            </button>
            <button
              disabled={!canIntervene || busy}
              onClick={() => onIntervention("crew")}
            >
              Add Crew {temporaryCrewId(scenario)} on first day
            </button>
          </div>
          {!canIntervene && (
            <small>
              Available after a recovery plan. Recorded demo supports N-02.
            </small>
          )}
          {cf && (
            <div className="reason" aria-live="polite">
              <strong>
                {cf.feasible
                  ? "Intervention feasible"
                  : "Intervention infeasible"}
              </strong>
              <p>{cf.summary}</p>
              <Validation plan={cf.result} />
            </div>
          )}
        </div>
      )}
      <details className="provenance">
        <summary>Data & assumptions</summary>
        {scenario.config.provenance.map((p) => (
          <p key={p.input}>
            <span className="badge">{p.kind}</span> {p.input}: {p.source}
          </p>
        ))}
        {plan?.assumptions.map((a) => (
          <p key={a.key}>
            <span className="badge">{a.kind}</span> {a.text}
          </p>
        ))}
      </details>
    </aside>
  );
}
