import { Status } from "../design/status";
import type { Plan, Scenario } from "../api/types";
export function SiteMap({
  scenario,
  plan,
  selected,
  onSelect,
}: {
  scenario: Scenario;
  plan: Plan | null;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const sites = scenario.sites.filter((s) => s.lon != null && s.lat != null);
  const coords = [
    ...sites.map((s) => [s.lon!, s.lat!]),
    ...scenario.clusters.flatMap((c) => c.outline ?? []),
  ];
  if (!coords.length)
    return (
      <section className="panel padded">No site coordinates available.</section>
    );
  const xs = coords.map((p) => p[0]),
    ys = coords.map((p) => p[1]);
  const minX = Math.min(...xs),
    maxY = Math.max(...ys),
    spanX = Math.max(...xs) - minX || 1,
    spanY = maxY - Math.min(...ys) || 1;
  const scale = Math.min(480 / spanX, 210 / spanY),
    x = (v: number) => 40 + (v - minX) * scale,
    y = (v: number) => 30 + (maxY - v) * scale;
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Service clusters</h2>
        <span>
          {scenario.config.synthetic ? "Synthetic geometry" : "Source geometry"}{" "}
          · select a site
        </span>
      </div>
      <div className="map-layout">
        <svg
          className="site-map"
          viewBox={`0 0 ${spanX * scale + 100} 270`}
          role="img"
          aria-label="Sites and service clusters"
        >
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
                {c.name}
              </text>
            </g>
          ))}
          {sites.map((s) => {
            const state =
              plan?.assignments.find((a) => a.site_id === s.site_id)?.state ??
              plan?.unscheduled.find((u) => u.site_id === s.site_id)?.state ??
              "unscheduled";
            return (
              <g
                key={s.site_id}
                role="button"
                tabIndex={0}
                aria-label={`Select ${s.site_id}, ${state}`}
                onClick={() => onSelect(s.site_id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(s.site_id);
                  }
                }}
                className={`map-point status-${state} ${selected === s.site_id ? "selected" : ""}`}
                transform={`translate(${x(s.lon!)},${y(s.lat!)})`}
              >
                <title>
                  {s.site_id}: {state}
                </title>
                <circle r={selected === s.site_id ? 8 : 5} />
              </g>
            );
          })}
        </svg>
        <div className="map-legend" aria-label="Site legend">
          {sites.map((site) => {
            const state =
              plan?.assignments.find((a) => a.site_id === site.site_id)
                ?.state ??
              plan?.unscheduled.find((u) => u.site_id === site.site_id)
                ?.state ??
              "unscheduled";
            return (
              <button
                key={site.site_id}
                aria-pressed={selected === site.site_id}
                onClick={() => onSelect(site.site_id)}
              >
                <strong className="mono">{site.site_id}</strong>
                <Status state={state} />
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
