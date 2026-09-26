import type { Plan } from "../api/types";
import { money } from "../lib/format";
export function MetricsStrip({ plan }: { plan: Plan | null }) {
  const o = plan?.objective;
  const metrics = [
    ["On time", o?.jobs_on_time, "commitments met"],
    [
      "Late",
      o?.jobs_late,
      o ? `${o.total_delay_days} total delay days` : "no feasible plan",
    ],
    ["Unscheduled", o?.jobs_unscheduled, o ? `${o.jobs_blocked} blocked` : "—"],
    [
      "Modeled value",
      o ? money(o.operating_value_usd) : undefined,
      o?.value_distinguishes_choices
        ? "value affects choices"
        : "equal values · no effect",
    ],
    [
      "Crew utilization",
      o ? `${Math.round(o.crew_utilization * 100)}%` : undefined,
      "on-site + travel",
    ],
    ["Moved installs", o?.changed_installs, "vs current install plan"],
  ];
  return (
    <section className="metrics" aria-label="Plan metrics">
      {metrics.map(([label, value, note]) => (
        <div key={String(label)}>
          <span className="eyebrow">{label}</span>
          <strong>{value ?? "—"}</strong>
          <small>{note}</small>
        </div>
      ))}
    </section>
  );
}
