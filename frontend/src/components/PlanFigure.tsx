import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Plan, Scenario, Schema } from "../api/types";
import { dateLabel, datesBetween } from "../lib/format";

export type CanvasTool =
  "knockout" | "halfday" | "long" | "reschedule" | "protect" | "trace";
export type PlanView = "crew" | "home";

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
  view,
  traceHomeId,
  selectedVisit,
  disabled,
  onView,
  onCrewDay,
  onVisit,
  onTrace,
}: {
  scenario: Scenario;
  option: Schema["RecoveryOption"] | undefined;
  comparisonOption?: Schema["RecoveryOption"] | null;
  disruption: Disruption[];
  tool: CanvasTool;
  view: PlanView;
  traceHomeId: string | null;
  selectedVisit: string | null;
  disabled: boolean;
  onView: (view: PlanView) => void;
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
    if (!plot || view !== "crew" || !traceKey) {
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
  }, [traceKey, view, option?.option_id, days.length]);

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

  const currentBatteryDay = (siteId: string, jobId?: string) => {
    const rows = scenario.current_plan.filter((row) => row.site_id === siteId);
    const site = scenario.sites.find(
      (candidate) => candidate.site_id === siteId,
    );
    const batteryJob = site?.visits.find(
      (visit) => visit.visit_type === "battery_day",
    )?.job_id;
    return (
      rows.find((row) => row.job_id === (jobId ?? batteryJob)) ??
      rows.find((row) => row.job_id === batteryJob) ??
      rows.find((row) => !row.job_id) ??
      rows[0]
    );
  };

  const homeRows = scenario.sites
    .map((site) => {
      const batteryJob = site.visits.find(
        (visit) => visit.visit_type === "battery_day",
      )?.job_id;
      const before = currentBatteryDay(site.site_id, batteryJob);
      const after = assignments.find(
        (assignment) =>
          assignment.site_id === site.site_id &&
          (assignment.job_id === batteryJob ||
            assignment.visit_type === "battery_day" ||
            (!batteryJob && !assignment.job_id)),
      );
      return {
        site,
        batteryJob,
        before,
        after,
        late: !after || after.days_late > 0,
      };
    })
    .sort(
      (left, right) =>
        Number(right.late) - Number(left.late) ||
        (right.after?.days_late ?? 0) - (left.after?.days_late ?? 0) ||
        left.site.site_id.localeCompare(right.site.site_id),
    );

  const start = Date.parse(`${scenario.config.planning_start}T12:00:00Z`);
  const end = Date.parse(`${scenario.config.planning_end}T12:00:00Z`);
  const dayPosition = (date?: string) => {
    if (!date || end <= start) return 0;
    return Math.max(
      0,
      Math.min(
        100,
        ((Date.parse(`${date}T12:00:00Z`) - start) / (end - start)) * 100,
      ),
    );
  };

  const handleHome = (siteId: string, jobId?: string) => {
    if (tool === "trace") {
      onTrace(siteId);
      return;
    }
    onVisit({
      site_id: siteId,
      job_id: jobId ?? null,
      crew_id: "",
      date: "",
      state: "scheduled",
      days_late: 0,
      value_usd: 0,
    });
  };

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
        <div className="view-switch" role="group" aria-label="Plan view">
          <button
            type="button"
            aria-pressed={view === "crew"}
            onClick={() => onView("crew")}
          >
            By crew
          </button>
          <button
            type="button"
            aria-pressed={view === "home"}
            onClick={() => onView("home")}
          >
            By home
          </button>
        </div>
      </header>
      <div className="figure-note">
        {view === "crew"
          ? comparisonOption
            ? "Darker visits moved from current plan. Arrow shows changes since previous plan."
            : "Click a crew-day or visit to apply the selected tool. Visit height shows on-site time."
          : comparisonOption
            ? "Battery-day marks compare the previous plan with this recovery and each home’s deadline."
            : "Battery days after recovery are compared with the current plan and each home’s deadline."}
      </div>
      <div
        className="visit-key"
        aria-label={view === "crew" ? "Visit types" : "Home timeline marks"}
      >
        {view === "crew" ? (
          <>
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
          </>
        ) : (
          <>
            <span>
              <i className="key-current" />
              {comparisonOption
                ? "Previous plan battery day"
                : "Current battery day"}
            </span>
            <span>
              <i className="key-recovered" />
              After recovery
            </span>
            <span>
              <i className="key-deadline" />
              Deadline
            </span>
          </>
        )}
        {traceHomeId && (
          <span className="trace-label">Tracing {traceHomeId}</span>
        )}
        <span className="cluster-key">
          Synthetic home prefixes: N North, S South, W West
        </span>
      </div>
      {view === "crew" ? (
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
                (edit) =>
                  edit.kind === "add_crew_day" && edit.crew_id === crewId,
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
                        assignment.crew_id === crewId &&
                        assignment.date === day,
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
                        ? Math.max(
                            0,
                            Math.min(100, (occupied / available) * 100),
                          )
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
                      (change) =>
                        (change.job_id ?? change.site_id) === traceKey,
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
                          style={{ height: `${capacityHeight}%` }}
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
                            const moveLabel =
                              change?.before && change.after
                                ? `${change.before.crew_id !== change.after.crew_id ? "crew swap" : `+${Math.max(0, Math.round((Date.parse(`${change.after.date}T12:00:00Z`) - Date.parse(`${change.before.date}T12:00:00Z`)) / 86400000))}d`}`
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
                                  {moveLabel && <small>{moveLabel}</small>}
                                </button>
                              </span>
                            );
                          })}
                        </span>
                        {pathOrigin && (
                          <span
                            className="move-origin-anchor"
                            data-old-key={
                              pathOrigin.job_id ?? pathOrigin.site_id
                            }
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
      ) : (
        <HomeTimeline
          scenario={scenario}
          option={option}
          comparisonOption={comparisonOption}
          traceHomeId={traceHomeId}
          disabled={disabled}
          onHome={handleHome}
          dayPosition={dayPosition}
          currentBatteryDay={currentBatteryDay}
        />
      )}
    </section>
  );
}

function HomeTimeline({
  scenario,
  option,
  comparisonOption,
  traceHomeId,
  disabled,
  onHome,
  dayPosition,
  currentBatteryDay,
}: {
  scenario: Scenario;
  option: Schema["RecoveryOption"] | undefined;
  comparisonOption?: Schema["RecoveryOption"] | null;
  traceHomeId: string | null;
  disabled: boolean;
  onHome: (siteId: string, jobId?: string) => void;
  dayPosition: (date?: string) => number;
  currentBatteryDay: (
    siteId: string,
    jobId?: string,
  ) => Schema["PlannedInstall"] | undefined;
}) {
  const finalAssignments = option?.result.assignments ?? [];
  const sites = scenario.sites
    .map((site) => {
      const batteryJobId = site.visits.find(
        (visit) => visit.visit_type === "battery_day",
      )?.job_id;
      const before = comparisonOption
        ? comparisonOption.result.assignments.find(
            (assignment) =>
              assignment.site_id === site.site_id &&
              (assignment.job_id === batteryJobId ||
                assignment.visit_type === "battery_day" ||
                (!batteryJobId && !assignment.job_id)),
          )
        : currentBatteryDay(site.site_id, batteryJobId);
      const after = finalAssignments.find(
        (assignment) =>
          assignment.site_id === site.site_id &&
          (assignment.job_id === batteryJobId ||
            assignment.visit_type === "battery_day" ||
            (!batteryJobId && !assignment.job_id)),
      );
      return {
        site,
        batteryJobId,
        before,
        after,
        late: !after || after.days_late > 0,
      };
    })
    .sort(
      (left, right) =>
        Number(right.late) - Number(left.late) ||
        (right.after?.days_late ?? 0) - (left.after?.days_late ?? 0) ||
        left.site.site_id.localeCompare(right.site.site_id),
    );
  const days = datesBetween(
    scenario.config.planning_start,
    scenario.config.planning_end,
  );
  return (
    <div className="home-plot">
      <div className="home-axis">
        <span>Home</span>
        <div
          style={{
            gridTemplateColumns: `repeat(${days.length}, minmax(0, 1fr))`,
          }}
        >
          {days.map((day) => (
            <span key={day}>{dateLabel(day)}</span>
          ))}
        </div>
      </div>
      {sites.map(({ site, batteryJobId, before, after, late }) => {
        const current = dayPosition(before?.date);
        const recovered = dayPosition(after?.date);
        const deadline = dayPosition(site.deadline);
        const beforeLabel = comparisonOption
          ? "Previous plan battery day"
          : "Current battery day";
        return (
          <button
            type="button"
            key={site.site_id}
            className={`home-row ${late ? "home-row-late" : ""} ${traceHomeId === site.site_id ? "home-row-traced" : ""}`}
            data-testid={`home-${site.site_id}`}
            aria-label={`${site.site_id}, ${comparisonOption ? "previous plan" : "current"} battery day ${before?.date ?? "none"}, after recovery ${after?.date ?? "none"}, deadline ${site.deadline}${late ? ", late or unassigned" : ""}`}
            disabled={disabled}
            onClick={() => onHome(site.site_id, batteryJobId)}
          >
            <strong>{site.site_id}</strong>
            <span className="home-track">
              <i
                className="home-deadline"
                style={{ left: `${deadline}%` }}
                title={`Deadline ${dateLabel(site.deadline)}`}
              />
              {before && (
                <i
                  className="home-current"
                  style={{ left: `${current}%` }}
                  title={`${beforeLabel} ${dateLabel(before.date)}`}
                />
              )}
              {after && (
                <i
                  className={`home-recovered ${late ? "home-recovered-late" : ""}`}
                  style={{ left: `${recovered}%` }}
                  title={`Battery day after recovery ${dateLabel(after.date)}`}
                />
              )}
              {traceHomeId === site.site_id && before && after && (
                <i
                  className="home-trace"
                  style={{
                    left: `${Math.min(current, recovered)}%`,
                    width: `${Math.max(0.8, Math.abs(current - recovered))}%`,
                  }}
                />
              )}
            </span>
            <span className="home-date">
              {after ? dateLabel(after.date) : "No battery day"}
            </span>
          </button>
        );
      })}
    </div>
  );
}
