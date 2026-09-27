import type { CanvasTool } from "./PlanFigure";

const tools: {
  id: CanvasTool;
  label: string;
  detail: string;
  target: string;
}[] = [
  {
    id: "knockout",
    label: "Knock out day",
    detail: "Remove this crew-day's capacity.",
    target: "Select a crew-day",
  },
  {
    id: "halfday",
    label: "Half day",
    detail: "Keep half of its available minutes.",
    target: "Select a crew-day",
  },
  {
    id: "long",
    label: "Runs long",
    detail: "Subtract this visit's duration from its crew-day.",
    target: "Select a visit",
  },
  {
    id: "reschedule",
    label: "Reschedule",
    detail: "Set this home's visits to start next business day.",
    target: "Select a home's visit",
  },
  {
    id: "protect",
    label: "Protect home",
    detail: "Pin its visits to their current crews and days.",
    target: "Select a home's visit",
  },
  {
    id: "trace",
    label: "Trace home",
    detail: "Compare its current and recovered battery day.",
    target: "Select a home's visit",
  },
];

export function TriggerRail({
  active,
  disabled,
  onSelect,
  onRandom,
  onReset,
}: {
  active: CanvasTool;
  disabled: boolean;
  onSelect: (tool: CanvasTool) => void;
  onRandom: () => void;
  onReset: () => void;
}) {
  const current = tools.find((tool) => tool.id === active);
  return (
    <nav className="trigger-rail" aria-label="Plan triggers">
      <div className="trigger-tools" role="group" aria-label="Choose a trigger">
        {tools.map((tool) => (
          <button
            type="button"
            key={tool.id}
            aria-pressed={active === tool.id}
            disabled={disabled}
            data-testid={`tool-${tool.id}`}
            onClick={() => onSelect(tool.id)}
            title={`${tool.label}: ${tool.detail}`}
          >
            <span className="trigger-label">{tool.label}</span>
            <small>{tool.detail}</small>
          </button>
        ))}
      </div>
      <span
        className="tool-help"
        aria-live="polite"
        data-testid="tool-instruction"
      >
        {current?.target}. {disabled ? "Recovery is being checked." : ""}
      </span>
      <div className="trigger-commands">
        <button
          type="button"
          disabled={disabled}
          onClick={onRandom}
          data-testid="random-trigger"
        >
          Random trigger
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={onReset}
          data-testid="reset-plan"
        >
          Reset
        </button>
      </div>
    </nav>
  );
}
