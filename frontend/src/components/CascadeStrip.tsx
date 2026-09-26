import type { Schema } from "../api/types";

export function CascadeStrip({
  cascade,
  selected,
  onSelect,
}: {
  cascade: Schema["ImpactAnalysis"]["cascade"];
  selected: number | null;
  onSelect: (index: number | null) => void;
}) {
  return (
    <section
      className="panel cascade-strip"
      aria-label="Disruption cascade"
      data-testid="cascade-strip"
    >
      <div className="panel-heading">
        <h2>Disruption cascade</h2>
        <button
          type="button"
          disabled={selected === null}
          onClick={() => onSelect(null)}
        >
          Clear highlight
        </button>
      </div>
      <ol>
        {cascade.map((step, index) => (
          <li key={`${step.kind}-${index}`}>
            <button
              type="button"
              aria-pressed={selected === index}
              data-testid={`cascade-${step.kind}`}
              className={selected === index ? "selected" : ""}
              onClick={() => onSelect(selected === index ? null : index)}
            >
              <span className="eyebrow">{step.kind}</span>
              <strong>{step.label}</strong>
              <small>{step.job_ids.length} visits or commitments</small>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}
