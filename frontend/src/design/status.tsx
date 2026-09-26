import type { Schema } from "../api/types";
export const statusLabels = {
  scheduled: "Scheduled",
  locked: "Locked",
  late: "Late",
  unscheduled: "Unscheduled",
  blocked: "Blocked",
};
export function Status({
  state,
  days = 0,
}: {
  state: Schema["JobState"];
  days?: number;
}) {
  return (
    <span className={`status status-${state}`}>
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        {state === "locked" ? (
          <>
            <path d="M3 5V3a3 3 0 016 0v2" fill="none" stroke="currentColor" />
            <rect x="2" y="5" width="8" height="7" rx="1" />
          </>
        ) : state === "late" ? (
          <path d="M6 1L12 11H0Z" />
        ) : state === "blocked" ? (
          <rect x="2" y="2" width="8" height="8" />
        ) : (
          <circle
            cx="6"
            cy="6"
            r="4"
            fill={state === "unscheduled" ? "none" : "currentColor"}
            stroke="currentColor"
          />
        )}
      </svg>
      {statusLabels[state]}
      {state === "late" && days > 0
        ? ` · ${days} ${days === 1 ? "day" : "days"}`
        : ""}
    </span>
  );
}
