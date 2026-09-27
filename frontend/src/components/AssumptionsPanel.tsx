import { useState } from "react";
import type { Schema } from "../api/types";
import { parseOverride } from "../lib/recovery";

export function AssumptionsPanel({
  assumptions,
  overrides,
  stub,
  recalculating,
  error,
  onApply,
  onReset,
}: {
  assumptions: Schema["EconomicAssumption"][];
  overrides: Record<string, number>;
  stub: boolean;
  recalculating: boolean;
  error: string | null;
  onApply: (values: Record<string, number>) => void;
  onReset: () => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  if (!assumptions.length) return null;
  const invalid = Object.entries(drafts)
    .filter(([, raw]) => parseOverride(raw) === null)
    .map(([key]) => key);
  const hasOverrides = Object.keys(overrides).length > 0;
  return (
    <details
      className="panel assumptions-panel"
      data-testid="assumptions-panel"
    >
      <summary>
        Economic assumptions {stub && <span className="badge">Stub data</span>}
        {hasOverrides && <span className="badge">Operator override</span>}
      </summary>
      <div className="assumption-list">
        {assumptions.map((assumption) => {
          const label = assumption.key.replaceAll("_", " ");
          const raw =
            drafts[assumption.key] ??
            String(overrides[assumption.key] ?? assumption.value);
          const bad = invalid.includes(assumption.key);
          return (
            <div className="assumption-row" key={assumption.key}>
              <label>
                <span>{label}</span>
                <span className="assumption-input">
                  <input
                    type="number"
                    min="0"
                    step="any"
                    value={raw}
                    disabled={!assumption.editable}
                    aria-label={label}
                    aria-invalid={bad}
                    onChange={(event) =>
                      setDrafts((current) => ({
                        ...current,
                        [assumption.key]: event.target.value,
                      }))
                    }
                  />
                  <small>{assumption.unit}</small>
                </span>
              </label>
              <span className="badge">
                {overrides[assumption.key] !== undefined
                  ? "Operator override"
                  : assumption.kind}
              </span>
              <small>
                {bad ? "Enter a number of 0 or more." : assumption.source}
              </small>
            </div>
          );
        })}
        {error && (
          <p role="alert" className="error" data-testid="economics-error">
            Could not recalculate with these assumptions: {error} The options
            shown use the last assumptions that worked.
          </p>
        )}
        {recalculating && (
          <p role="status" data-testid="economics-recalculating">
            Recalculating modeled costs…
          </p>
        )}
        <div className="actions">
          <button
            type="button"
            disabled={invalid.length > 0 || recalculating}
            onClick={() => {
              const values: Record<string, number> = { ...overrides };
              for (const [key, raw] of Object.entries(drafts)) {
                const value = parseOverride(raw);
                if (value !== null) values[key] = value;
              }
              onApply(values);
            }}
            data-testid="apply-economics"
          >
            Apply modeled costs
          </button>
          <button
            type="button"
            disabled={!hasOverrides && !Object.keys(drafts).length}
            onClick={() => {
              setDrafts({});
              onReset();
            }}
            data-testid="reset-economics"
          >
            Reset assumptions
          </button>
        </div>
      </div>
    </details>
  );
}
