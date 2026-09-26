import type { Schema } from "../api/types";
export function ComparePanel({ diff }: { diff: Schema["PlanDiff"] }) {
  return (
    <section className="panel compare">
      <div className="panel-heading">
        <h2>Recovery changes</h2>
        <span>Compared with the pinned baseline</span>
      </div>
      <p>{diff.headline}</p>
      <ul>
        {diff.changes.map((c, i) => (
          <li key={i}>
            <strong className="mono">{c.site_id}</strong>
            <span>{c.note}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
