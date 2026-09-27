import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Plan, Scenario, Schema } from "../api/types";
import { dateLabel, datesBetween } from "../lib/format";
import { slotsOffPlan } from "../lib/recovery";

export type CanvasTool =
  "knockout" | "halfday" | "long" | "reschedule" | "protect" | "trace";

type Assignment = Plan["assignments"][number];
type Disruption = Schema["RecoveryOptionsRequest"]["disruption"][number];
type RecoveryOption = Schema["RecoveryOption"];
type MovementChange = Pick<
  Schema["PlanDiff"]["changes"][number],
  "after" | "before" | "job_id" | "kind" | "site_id"
>;

function compareOptions(
  beforeOption: RecoveryOption,
  afterOption: RecoveryOption | undefined,
): MovementChange[] {
  if (!afterOption) return [];
  const beforeByJob = new Map(
    beforeOption.result.assignments.map((assignment) => [
      assignment.job_id ?? assignment.site_id,
      assignment,
    ]),
  );
  return afterOption.result.assignments.flatMap((after) => {
    const before = beforeByJob.get(after.job_id ?? after.site_id);
    if (
      !before ||
      (before.crew_id === after.crew_id && before.date === after.date)
    ) {
      return [];
    }
    return [
      {
        job_id: after.job_id ?? before.job_id,
        site_id: after.site_id,
        kind: "moved" as const,
        before: { crew_id: before.crew_id, date: before.date },
        after: { crew_id: after.crew_id, date: after.date },
      },
    ];
  });
}

export function PlanFigure({
  scenario,
  option,
  comparisonOption,
  disruption,
  tool,
  traceHomeId,
  selectedVisit,
  disabled,
  onCrewDay,
  onVisit,
  onTrace,
}: {
  scenario: Scenario;
  option: Schema["RecoveryOption"] | undefined;
  comparisonOption?: Schema["RecoveryOption"] | null;
  disruption: Disruption[];
  tool: CanvasTool;
  traceHomeId: string | null;
  selectedVisit: string | null;
  disabled: boolean;
  onCrewDay: (crewId: string, date: string, availableMin: number) => void;
  onVisit: (assignment: Assignment) => void;
  onTrace: (siteId: string) => void;
}) {
  const [hoveredVisit, setHoveredVisit] = useState<string | null>(null);
  const [arrivalKey, setArrivalKey] = useState<string | null>(null);
  const plotRef = useRef<HTMLDivElement>(null);
  const previousOptionId = useRef<string | null>(null);
  const [tracePath, setTracePath] = useState("");
  const result = option?.result;
  const days = datesBetween(
    scenario.config.planning_start,
    scenario.config.planning_end,
  );
  const assignments = result?.assignments ?? [];
  const cumulativeChanges = option?.diff_vs_original.changes ?? [];
  const ghosts = option ? slotsOffPlan(option) : [];
  const transitionChanges = comparisonOption
    ? compareOptions(comparisonOption, option)
    : cumulativeChanges;
  useEffect(() => {
    const optionId = option?.option_id ?? null;
    const previousId = previousOptionId.current;
    previousOptionId.current = optionId;
    if (!previousId || !optionId || previousId === optionId) return;

    const firstMove = transitionChanges.find(
      (change) => change.kind === "moved" && change.before && change.after,
    );
    if (!firstMove) return;

    const key = firstMove.job_id ?? firstMove.site_id;
    setArrivalKey(key);
    const timeout = window.setTimeout(() => setArrivalKey(null), 1400);
    return () => window.clearTimeout(timeout);
  }, [comparisonOption?.option_id, option?.option_id]);
  const traceChange =
    transitionChanges.find(
      (change) =>
        (change.job_id ?? change.site_id) === hoveredVisit &&
        change.kind === "moved" &&
        change.before &&
        change.after,
    ) ??
    (traceHomeId
      ? transitionChanges.find(
          (change) =>
            change.site_id === traceHomeId &&
            change.kind === "moved" &&
            change.before &&
            change.after,
        )
      : undefined);
  const arrivalChange = arrivalKey
    ? transitionChanges.find(
        (change) =>
          (change.job_id ?? change.site_id) === arrivalKey &&
          change.kind === "moved" &&
          change.before &&
          change.after,
      )
    : undefined;
  const currentTraceChange = traceChange ?? arrivalChange;
  const traceKey = currentTraceChange?.job_id ?? currentTraceChange?.site_id;

  useLayoutEffect(() => {
    const plot = plotRef.current;
    if (!plot || !traceKey) {
      setTracePath("");
      return;
    }
    const oldMark = Array.from(
      plot.querySelectorAll<HTMLElement>("[data-old-key]"),
    ).find((mark) => mark.dataset.oldKey === traceKey);
    const newMark = plot.querySelector<HTMLElement>(
      `[data-new-key="${traceKey}"]`,
    );
    if (!oldMark || !newMark) {
      setTracePath("");
      return;
    }
    const bounds = plot.getBoundingClientRect();
    const oldBox = oldMark.getBoundingClientRect();
    const newBox = newMark.getBoundingClientRect();
    const x1 = oldBox.left + oldBox.width / 2 - bounds.left;
    const y1 = oldBox.top + oldBox.height / 2 - bounds.top;
    const x2 = newBox.left + newBox.width / 2 - bounds.left;
    const y2 = newBox.top + newBox.height / 2 - bounds.top;
    const bend = Math.max(18, Math.abs(x2 - x1) * 0.35);
    setTracePath(
      `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`,
    );
  }, [traceKey, option?.option_id, days.length]);

  const crewIds = [
    ...new Set([
      ...scenario.crew_days.map((day) => day.crew_id),
      ...(result?.crew_days.map((day) => day.crew_id) ?? []),
    ]),
  ].sort((left, right) => {
    const skillRank = (crewId: string) => {
      const added = option?.intervention_edits.find(
        (edit) => edit.kind === "add_crew_day" && edit.crew_id === crewId,
      );
      const skills =
        added?.kind === "add_crew_day"
          ? added.skills
          : scenario.crew_days
              .filter((day) => day.crew_id === crewId)
              .flatMap((day) => day.skills);
      return skills.includes("install")
        ? 0
        : skills.includes("battery")
          ? 1
          : 2;
    };
    return skillRank(left) - skillRank(right) || left.localeCompare(right);
  });

  return (
    <section
      className="plan-figure"
      aria-label="Recovery plan figure"
      data-testid="plan-figure"
    >
      <header className="figure-heading">
        <div>
          <span className="figure-number">Figure 1</span>
          <h2>Plan by crew and day</h2>
        </div>
      </header>
      <div className="figure-note">
        {comparisonOption
          ? "Darker visits moved from current plan. Arrow shows changes since previous plan."
          : "Click a crew-day or visit to apply the selected tool. Visit height shows on-site time."}
      </div>
      <div className="visit-key" aria-label="Visit types">
        <span>
          <i className="key-install" />
          Install
        </span>
        <span>
          <i className="key-battery" />
          Battery day
        </span>
        <span>
          <i className="key-deadline" />
          Missed deadline
        </span>
        {traceHomeId && (
          <span className="trace-label">Tracing {traceHomeId}</span>
        )}
        <span className="cluster-key">
          Synthetic home prefixes: N North, S South, W West
        </span>
      </div>
      <div className="crew-plot" ref={plotRef} data-tool={tool}>
        <div
          className="crew-grid crew-date-axis"
          style={{
            gridTemplateColumns: `72px repeat(${days.length}, minmax(0, 1fr))`,
          }}
        >
          <span className="axis-corner">Crew</span>
          {days.map((day) => (
            <span className="axis-date" key={day}>
              {dateLabel(day)}
            </span>
          ))}
        </div>
        <div
          className="crew-grid crew-rows"
          style={{
            gridTemplateColumns: `72px repeat(${days.length}, minmax(0, 1fr))`,
          }}
        >
          {crewIds.map((crewId) => {
            const added = option?.intervention_edits.find(
              (edit) => edit.kind === "add_crew_day" && edit.crew_id === crewId,
            );
            const skills =
              added?.kind === "add_crew_day"
                ? added.skills
                : scenario.crew_days
                    .filter((day) => day.crew_id === crewId)
                    .flatMap((day) => day.skills);
            const skill = skills.includes("install")
              ? "Install crew"
              : skills.includes("battery")
                ? "Battery crew"
                : "Temporary crew";
            return (
              <div className="crew-row-fragment" key={crewId}>
                <div className="crew-label">
                  <strong>{crewId}</strong>
                  <small>{skill}</small>
                </div>
                {days.map((day) => {
                  const base = scenario.crew_days.find(
                    (entry) => entry.crew_id === crewId && entry.date === day,
                  );
                  const usage = result?.crew_days.find(
                    (entry) => entry.crew_id === crewId && entry.date === day,
                  );
                  const changed = disruption.find(
                    (edit) =>
                      (edit.kind === "remove_crew_day" ||
                        edit.kind === "reduce_crew_day") &&
                      edit.crew_id === crewId &&
                      edit.date === day,
                  );
                  const available =
                    usage?.available_min ??
                    (changed?.kind === "remove_crew_day"
                      ? 0
                      : (base?.available_min ?? 0));
                  const visits = assignments.filter(
                    (assignment) =>
                      assignment.crew_id === crewId && assignment.date === day,
                  );
                  const occupied = visits.reduce((sum, assignment) => {
                    const site = scenario.sites.find(
                      (entry) => entry.site_id === assignment.site_id,
                    );
                    return (
                      sum +
                      (site?.visits.find(
                        (visit) => visit.job_id === assignment.job_id,
                      )?.duration_min ??
                        site?.duration_min ??
                        0)
                    );
                  }, 0);
                  const capacityHeight =
                    available > 0
                      ? Math.max(0, Math.min(100, (occupied / available) * 100))
                      : 0;
                  const lost =
                    changed?.kind === "remove_crew_day" ||
                    (changed?.kind === "reduce_crew_day" &&
                      !!base &&
                      changed.available_min < base.available_min);
                  const departed = transitionChanges.filter(
                    (change) =>
                      change.kind === "moved" &&
                      change.before?.crew_id === crewId &&
                      change.before.date === day &&
                      change.after &&
                      (change.after.crew_id !== crewId ||
                        change.after.date !== day),
                  );
                  const pathOrigin = departed.find(
                    (change) => (change.job_id ?? change.site_id) === traceKey,
                  );
                  return (
                    <div
                      key={day}
                      className={`crew-day ${lost ? "crew-day-lost" : ""} ${available === 0 ? "crew-day-off" : ""}`}
                      data-crew-id={crewId}
                      data-date={day}
                      data-testid={`crew-day-${crewId}-${day}`}
                    >
                      <button
                        type="button"
                        className="crew-day-action"
                        aria-label={`${crewId} ${dateLabel(day)}, ${available} min available`}
                        disabled={disabled || !base || available === 0}
                        onClick={() => onCrewDay(crewId, day, available)}
                      />
                      <span className="capacity-track">
                        <span
                          className="capacity-fill"
                          style={{ height: `${capacityHeight}%` }}
                        />
                      </span>
                      <span
                        className="visit-stack"
                        style={{
                          minHeight: `calc((100% - 20px) * ${capacityHeight / 100})`,
                        }}
                      >
                        {visits.map((assignment) => {
                          const key = assignment.job_id ?? assignment.site_id;
                          const site = scenario.sites.find(
                            (entry) => entry.site_id === assignment.site_id,
                          );
                          const visit = site?.visits.find(
                            (entry) => entry.job_id === assignment.job_id,
                          );
                          const cumulativeChange = cumulativeChanges.find(
                            (entry) =>
                              (entry.job_id ?? entry.site_id) === key &&
                              entry.kind === "moved",
                          );
                          const change = transitionChanges.find(
                            (entry) =>
                              (entry.job_id ?? entry.site_id) === key &&
                              entry.kind === "moved",
                          );
                          const crewSwap =
                            change?.before &&
                            change.after &&
                            change.before.crew_id !== change.after.crew_id;
                          const shiftDays =
                            change?.before && change.after && !crewSwap
                              ? Math.max(
                                  0,
                                  Math.round(
                                    (Date.parse(
                                      `${change.after.date}T12:00:00Z`,
                                    ) -
                                      Date.parse(
                                        `${change.before.date}T12:00:00Z`,
                                      )) /
                                      86400000,
                                  ),
                                )
                              : 0;
                          const moveLabel = crewSwap
                            ? "crew swap"
                            : change?.before && change.after
                              ? `+${shiftDays}d`
                              : "";
                          return (
                            <span
                              key={key}
                              className={`visit-mark ${assignment.visit_type === "install" ? "visit-install" : "visit-battery"} ${assignment.days_late > 0 ? "visit-late" : ""} ${cumulativeChange ? "visit-moved" : ""} ${selectedVisit === key ? "visit-selected" : ""}`}
                              style={{
                                flex: `${Math.max(1, visit?.duration_min ?? site?.duration_min ?? 1)} 1 0`,
                              }}
                            >
                              <button
                                type="button"
                                data-new-key={key}
                                data-state={assignment.state}
                                aria-label={`${assignment.site_id} ${assignment.visit_type ?? "visit"}, ${crewId} ${dateLabel(day)}${moveLabel ? `, moved ${moveLabel}` : ""}`}
                                title={
                                  change?.before
                                    ? `Formerly ${change.before.crew_id} ${dateLabel(change.before.date)}`
                                    : `${crewId} ${dateLabel(day)}`
                                }
                                onPointerEnter={() => setHoveredVisit(key)}
                                onPointerLeave={() => setHoveredVisit(null)}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  tool === "trace"
                                    ? onTrace(assignment.site_id)
                                    : onVisit(assignment);
                                }}
                                disabled={disabled}
                              >
                                <span>{assignment.site_id}</span>
                                {moveLabel && (
                                  <small
                                    className={`move-badge ${shiftDays > 0 ? "move-badge-late" : ""}`}
                                  >
                                    {moveLabel}
                                  </small>
                                )}
                              </button>
                            </span>
                          );
                        })}
                      </span>
                      {lost && (
                        <span
                          className="lost-ghosts"
                          data-testid={`lost-capacity-${crewId}-${day}`}
                        >
                          {ghosts
                            .filter(
                              (ghost) =>
                                ghost.crew_id === crewId && ghost.date === day,
                            )
                            .map((ghost) => (
                              <span
                                key={ghost.job_id}
                                className="lost-ghost"
                                data-testid={`ghost-${ghost.job_id}`}
                                title={`${ghost.site_id} was planned here. It ${ghost.kind === "moved" ? "moved" : "has no slot"} after recovery.`}
                              >
                                {ghost.site_id}
                              </span>
                            ))}
                        </span>
                      )}
                      {pathOrigin && (
                        <span
                          className="move-origin-anchor"
                          data-old-key={pathOrigin.job_id ?? pathOrigin.site_id}
                          aria-hidden="true"
                        />
                      )}
                      {available === 0 ? (
                        <span className="off-label">Off</span>
                      ) : (
                        <span className="capacity-label">
                          {occupied}/{available} min
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </div>
        {tracePath && (
          <svg
            className={`trace-overlay ${arrivalKey === traceKey ? "trace-overlay-arrival" : ""}`}
            aria-hidden="true"
          >
            <path d={tracePath} pathLength={1} />
          </svg>
        )}
      </div>
    </section>
  );
}
