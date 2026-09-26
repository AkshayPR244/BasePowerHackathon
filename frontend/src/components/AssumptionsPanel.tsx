import { useState } from "react";
import type { Schema } from "../api/types";

export function AssumptionsPanel({
  assumptions,
  overrides,
  stub,
  onApply,
}: {
  assumptions: Schema["EconomicAssumption"][];
  overrides: Record<string, number>;
  stub: boolean;
  onApply: (values: Record<string, number>) => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, number>>({});
  if (!assumptions.length) return null;
  return (
    <details
      className="panel assumptions-panel"
      data-testid="assumptions-panel"
    >
      <summary>
        Economic assumptions {stub && <span className="badge">Stub data</span>}
      </summary>
      <div className="assumption-list">
        {assumptions.map((assumption) => {
          const value =
            drafts[assumption.key] ??
            overrides[assumption.key] ??
            assumption.value;
          return (
            <div className="assumption-row" key={assumption.key}>
              <label>
                <span>{assumption.key.replaceAll("_", " ")}</span>
                <span className="assumption-input">
                  <input
                    type="number"
                    min="0"
                    step="any"
                    value={value}
                    disabled={!assumption.editable}
                    aria-label={assumption.key.replaceAll("_", " ")}
                    onChange={(event) =>
                      setDrafts((current) => ({
                        ...current,
                        [assumption.key]: Number(event.target.value),
                      }))
                    }
                  />
                  <small>{assumption.unit}</small>
                </span>
              </label>
              <span className="badge">{assumption.kind}</span>
              <small>{assumption.source}</small>
            </div>
          );
        })}
        <button
          type="button"
          onClick={() => onApply({ ...overrides, ...drafts })}
          data-testid="apply-economics"
        >
          Apply modeled costs
        </button>
      </div>
    </details>
  );
}
