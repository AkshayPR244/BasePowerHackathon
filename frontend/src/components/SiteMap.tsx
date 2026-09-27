import { Status } from "../design/status";
import type { Plan, Scenario } from "../api/types";
import {
  clusterDirection,
  clusterKey,
  HOUSTON_CENTER,
  isHoustonScenario,
} from "../lib/geography";
export function SiteMap({
  scenario,
  plan,
  selected,
  affectedJobIds = [],
  compact = false,
  noPlanLabel = "No valid plan",
  onSelect,
}: {
  scenario: Scenario;
  plan: Plan | null;
  selected: string | null;
  affectedJobIds?: string[];
  compact?: boolean;
  noPlanLabel?: string;
  onSelect: (id: string) => void;
}) {
  const stateOf = (siteId: string) =>
    plan
      ? (plan.assignments.find((a) => a.site_id === siteId)?.state ??
        plan.unscheduled.find((u) => u.site_id === siteId)?.state ??
        "unscheduled")
      : null;
  const sites = scenario.sites.filter((s) => s.lon != null && s.lat != null);
  const affected = (siteId: string) =>
    affectedJobIds.some(
      (jobId) => jobId === siteId || jobId.startsWith(`${siteId}-`),
    );
  const houston = isHoustonScenario(scenario);
  const coords = [
    ...sites.map((s) => [s.lon!, s.lat!]),
    ...scenario.clusters.flatMap((c) => c.outline ?? []),
    ...(houston ? [[HOUSTON_CENTER.lon, HOUSTON_CENTER.lat]] : []),
  ];
  if (!coords.length)
    return (
      <section className="panel padded">No site coordinates available.</section>
    );
  const xs = coords.map((p) => p[0]),
    ys = coords.map((p) => p[1]);
  const centerX = houston
      ? HOUSTON_CENTER.lon
      : (Math.min(...xs) + Math.max(...xs)) / 2,
    centerY = houston
      ? HOUSTON_CENTER.lat
      : (Math.min(...ys) + Math.max(...ys)) / 2,
    halfX = Math.max(...xs.map((value) => Math.abs(value - centerX)), 0.01),
    halfY = Math.max(...ys.map((value) => Math.abs(value - centerY)), 0.01),
    minX = centerX - halfX,
    maxY = centerY + halfY,
    spanX = halfX * 2,
    spanY = halfY * 2;
  const scale = Math.min(480 / spanX, 210 / spanY),
    x = (v: number) => 40 + (v - minX) * scale,
    y = (v: number) => 30 + (maxY - v) * scale;
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>{houston ? "Houston service clusters" : "Service clusters"}</h2>
        <span>
          {scenario.config.synthetic ? "Synthetic geometry" : "Source geometry"}{" "}
          · {clusterKey(scenario)} · select a site
        </span>
      </div>
      <div className={compact ? "map-layout compact" : "map-layout"}>
        <svg
          className="site-map"
          viewBox={`0 0 ${spanX * scale + 100} 270`}
          role="img"
          aria-label={`${houston ? "Houston-centered " : ""}sites and service clusters`}
        >
          {houston && (
            <g
              className="houston-center"
              transform={`translate(${x(HOUSTON_CENTER.lon)},${y(HOUSTON_CENTER.lat)})`}
              aria-label="Houston center"
            >
              <circle r="5" />
              <path d="M -9 0 H 9 M 0 -9 V 9" />
              <text x="9" y="-9">
                Houston center
              </text>
            </g>
          )}
          <g className="map-compass" aria-hidden="true">
            <path d="M 24 47 V 17 M 24 17 L 19 25 M 24 17 L 29 25" />
            <text x="24" y="12" textAnchor="middle">
              N
            </text>
            <text x="38" y="36" textAnchor="middle">
              E
            </text>
            <text x="24" y="58" textAnchor="middle">
              S
            </text>
            <text x="10" y="36" textAnchor="middle">
              W
            </text>
          </g>
          {scenario.clusters.map((c) => (
            <g key={c.cluster_id}>
              <polygon
                points={(c.outline ?? [])
                  .map((p) => `${x(p[0])},${y(p[1])}`)
                  .join(" ")}
                className="cluster"
              />
              <text
                x={x(c.outline?.[0]?.[0] ?? minX) + 10}
                y={y(c.outline?.[0]?.[1] ?? maxY) + 20}
              >
                {c.cluster_id} · {clusterDirection(c.cluster_id, c.name)}
              </text>
            </g>
          ))}
          {sites.map((s) => {
            const state = stateOf(s.site_id);
            const isAffected = affected(s.site_id);
            return (
              <g
                key={s.site_id}
                role="button"
                tabIndex={0}
                aria-label={`Select ${s.site_id}, ${state ?? noPlanLabel.toLowerCase()}${isAffected ? ", affected by disruption" : ""}`}
                onClick={() => onSelect(s.site_id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(s.site_id);
                  }
                }}
                className={`map-point status-${state ?? "none"} ${selected === s.site_id ? "selected" : ""} ${isAffected ? "affected" : ""}`}
                transform={`translate(${x(s.lon!)},${y(s.lat!)})`}
              >
                <title>
                  {s.site_id}: {state ?? noPlanLabel}
                </title>
                <circle r={selected === s.site_id ? 8 : 5} />
              </g>
            );
          })}
        </svg>
        {!compact && (
          <div className="map-legend" aria-label="Site legend">
            {sites.map((site) => {
              const state = stateOf(site.site_id);
              return (
                <button
                  key={site.site_id}
                  aria-pressed={selected === site.site_id}
                  onClick={() => onSelect(site.site_id)}
                >
                  <strong className="mono">{site.site_id}</strong>
                  {state ? (
                    <Status state={state} />
                  ) : (
                    <span className="muted">{noPlanLabel}</span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
      {affectedJobIds.length > 0 && (
        <div
          className="affected-inset"
          data-testid="affected-map-inset"
          aria-label="Affected homes by cluster"
        >
          <span className="eyebrow">Affected homes by cluster</span>
          {scenario.clusters.map((cluster) => {
            const homes = scenario.sites.filter(
              (site) =>
                site.cluster_id === cluster.cluster_id &&
                affected(site.site_id),
            );
            return (
              <div className="affected-cluster" key={cluster.cluster_id}>
                <strong>{cluster.name}</strong>
                <span>{homes.length} affected homes</span>
                <small>
                  {homes.map((site) => site.site_id).join(" · ") || "None"}
                </small>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
