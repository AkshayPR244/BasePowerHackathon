import type { Plan } from "../api/types";
import { Status } from "../design/status";
export function DeferredList({
  plan,
  onSelect,
}: {
  plan: Plan | null;
  onSelect: (id: string) => void;
}) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Deferred & blocked</h2>
        <span>{plan?.unscheduled.length ?? 0} sites</span>
      </div>
      {plan?.unscheduled.map((job) => (
        <button
          className="deferred"
          key={job.site_id}
          onClick={() => onSelect(job.site_id)}
        >
          <div>
            <strong className="mono">{job.site_id}</strong>
            <Status state={job.state} />
          </div>
          <p>{job.detail}</p>
          <code>{job.reasons.join(" · ")}</code>
        </button>
      ))}
      {!plan?.unscheduled.length && (
        <p className="empty padded">No deferred jobs in this result.</p>
      )}
    </section>
  );
}
