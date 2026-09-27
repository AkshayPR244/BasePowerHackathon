import type { Schema } from "../api/types";
import { adjustedCostClass } from "../lib/format";

type RecoveryOption = Schema["RecoveryOption"];

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function isPlottable(option: RecoveryOption) {
  return (
    (option.status === "optimal" || option.status === "feasible") &&
    option.result.objective !== null &&
    option.result.validation.checked &&
    option.result.validation.valid
  );
}

export function OptionFrontier({
  options,
  selectedId,
  customLabel,
  onSelect,
}: {
  options: RecoveryOption[];
  selectedId: string | null;
  customLabel?: string;
  onSelect: (optionId: string) => void;
}) {
  const plotted = options.filter(isPlottable);
  const costs = plotted.map((option) => option.economics.net_impact_usd);
  const minimumCost = Math.min(0, ...costs);
  const maximumCost = Math.max(1, ...costs);
  const costRange = maximumCost - minimumCost || 1;
  const maximumMissed = Math.max(
    1,
    ...plotted.map((option) => option.counts.deadlines_missed),
  );
  const left = 43;
  const right = 12;
  const top = 20;
  const bottom = 38;
  const width = 420;
  const height = 300;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const point = (option: RecoveryOption) => ({
    x:
      left +
      ((option.economics.net_impact_usd - minimumCost) / costRange) * plotWidth,
    y:
      top +
      plotHeight -
      (option.counts.deadlines_missed / maximumMissed) * plotHeight,
  });
  const frontier = plotted
    .filter(
      (candidate) =>
        !plotted.some(
          (other) =>
            other.option_id !== candidate.option_id &&
            other.economics.net_impact_usd <=
              candidate.economics.net_impact_usd &&
            other.counts.deadlines_missed <=
              candidate.counts.deadlines_missed &&
            (other.economics.net_impact_usd <
              candidate.economics.net_impact_usd ||
              other.counts.deadlines_missed <
                candidate.counts.deadlines_missed),
        ),
    )
    .sort((a, b) => a.economics.net_impact_usd - b.economics.net_impact_usd);
  const frontierPoints = frontier.map((option) => {
    const coordinate = point(option);
    return `${coordinate.x},${coordinate.y}`;
  });
  const overlapCounts = new Map<string, number>();
  for (const option of plotted) {
    const key = `${option.economics.net_impact_usd}|${option.counts.deadlines_missed}`;
    overlapCounts.set(key, (overlapCounts.get(key) ?? 0) + 1);
  }
  const overlapIndexes = new Map<string, number>();
  const plotEntries = plotted.map((option) => {
    const origin = point(option);
    const key = `${option.economics.net_impact_usd}|${option.counts.deadlines_missed}`;
    const total = overlapCounts.get(key) ?? 1;
    const index = overlapIndexes.get(key) ?? 0;
    overlapIndexes.set(key, index + 1);
    if (total === 1) return { option, origin, marker: origin, overlaps: false };
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / total;
    const spread = Math.min(14, 8 + total);
    return {
      option,
      origin,
      marker: {
        x: origin.x + Math.cos(angle) * spread,
        y: origin.y + Math.sin(angle) * spread,
      },
      overlaps: true,
    };
  });
  const formatCost = (value: number) => money.format(value);
  const label = (option: RecoveryOption) =>
    option.kind === "no_action"
      ? "No action"
      : option.kind === "custom" && customLabel
        ? customLabel
        : option.action_label.replace(/ \([^)]*\)/g, "");
  const unchecked = options.length - plotted.length;

  return (
    <section
      className="frontier-figure"
      aria-label="Recovery options figure"
      data-testid="option-frontier"
    >
      <header className="figure-heading">
        <div>
          <span className="figure-number">Figure 2</span>
          <h2>Recovery options</h2>
        </div>
      </header>
      <p className="figure-note">
        Points match the options below. Lower-left is better. Size shows
        customers to reschedule. Adjusted cost includes operating-value changes
        calculated from 2018 ERCOT hindsight prices.
      </p>
      {plotted.length > 0 ? (
        <>
          <svg
            className="frontier-svg"
            viewBox={`0 0 ${width} ${height}`}
            role="group"
            aria-label="Adjusted cost versus the original plan by deadlines missed; dot size shows customers to reschedule"
          >
            {[0, 0.5, 1].map((fraction) => {
              const y = top + plotHeight * (1 - fraction);
              const missed = Math.round(maximumMissed * fraction);
              return (
                <g key={fraction}>
                  <line
                    className="plot-grid"
                    x1={left}
                    x2={width - right}
                    y1={y}
                    y2={y}
                  />
                  <text
                    className="plot-tick"
                    x={left - 8}
                    y={y + 3}
                    textAnchor="end"
                  >
                    {missed}
                  </text>
                </g>
              );
            })}
            {[0, 0.5, 1].map((fraction) => {
              const x = left + plotWidth * fraction;
              const cost = minimumCost + costRange * fraction;
              return (
                <g key={fraction}>
                  <line
                    className="plot-grid plot-grid-vertical"
                    x1={x}
                    x2={x}
                    y1={top}
                    y2={top + plotHeight}
                  />
                  <text
                    className="plot-tick"
                    x={x}
                    y={top + plotHeight + 16}
                    textAnchor="middle"
                  >
                    {formatCost(cost)}
                  </text>
                </g>
              );
            })}
            <text
              className="plot-axis-label"
              x={left + plotWidth / 2}
              y={height - 4}
              textAnchor="middle"
            >
              Adjusted cost vs original plan
            </text>
            <text
              className="plot-axis-label"
              transform={`translate(12 ${top + plotHeight / 2}) rotate(-90)`}
              textAnchor="middle"
            >
              Deadlines missed
            </text>
            {frontierPoints.length > 1 && (
              <polyline
                className="frontier-line"
                points={frontierPoints.join(" ")}
              />
            )}
            {plotEntries.map(({ option, origin, marker, overlaps }) => {
              const radius =
                5 + Math.sqrt(option.counts.customers_to_reschedule) * 1.15;
              const selected = selectedId === option.option_id;
              const isNoAction = option.kind === "no_action";
              return (
                <g
                  key={option.option_id}
                  role="button"
                  tabIndex={0}
                  aria-label={`${label(option)}, ${formatCost(option.economics.net_impact_usd)} adjusted cost versus the original plan, ${option.counts.deadlines_missed} deadlines missed, ${option.counts.customers_to_reschedule} customers to reschedule`}
                  aria-pressed={selected}
                  data-option-id={option.option_id}
                  data-option-kind={option.kind}
                  className={`frontier-point ${adjustedCostClass(option.economics.net_impact_usd)} ${isNoAction ? "frontier-no-action" : ""} ${selected ? "frontier-selected" : ""}`}
                  style={{ pointerEvents: "all" }}
                  onClick={() => onSelect(option.option_id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelect(option.option_id);
                    }
                  }}
                >
                  <title>
                    {`${label(option)}, ${formatCost(option.economics.net_impact_usd)} adjusted cost versus the original plan, ${option.counts.deadlines_missed} deadlines missed`}
                  </title>
                  {overlaps && (
                    <line
                      className="frontier-overlap-link"
                      x1={origin.x}
                      y1={origin.y}
                      x2={marker.x}
                      y2={marker.y}
                    />
                  )}
                  <circle
                    className="frontier-halo"
                    cx={marker.x}
                    cy={marker.y}
                    r={radius + 1}
                  />
                  <circle
                    className="frontier-marker"
                    cx={marker.x}
                    cy={marker.y}
                    r={radius}
                  />
                </g>
              );
            })}
          </svg>
          <div className="option-chips" aria-label="Recovery option selection">
            {plotted.map((option) => (
              <button
                type="button"
                key={option.option_id}
                data-option-kind={option.kind}
                aria-pressed={selectedId === option.option_id}
                className={`option-chip ${selectedId === option.option_id ? "option-chip-selected" : ""}`}
                onClick={() => onSelect(option.option_id)}
              >
                <span className="option-chip-heading">
                  <span className="option-chip-swatch" aria-hidden="true" />
                  <span>{label(option)}</span>
                </span>
                {option.lowest_modeled_cost && (
                  <small>Lowest adjusted cost</small>
                )}
              </button>
            ))}
          </div>
          <p className="size-note">
            Larger dot = more customers to reschedule.
          </p>
        </>
      ) : (
        <p className="figure-empty">
          No feasible, validated option is available.
        </p>
      )}
      {unchecked > 0 && (
        <p className="figure-warning">
          {unchecked} option{unchecked === 1 ? " was" : "s were"} withheld
          because validation did not pass.
        </p>
      )}
    </section>
  );
}
