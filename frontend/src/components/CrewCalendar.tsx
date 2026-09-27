import { useLayoutEffect, useRef, useState } from "react";
import type { Plan, Scenario } from "../api/types";
import { datesBetween, dateLabel } from "../lib/format";
import { Status } from "../design/status";

export type GhostSlot = {
  job_id: string;
  site_id: string;
  crew_id: string;
  date: string;
  kind: string;
};

const matchesJob = (ids: Set<string>, jobId: string, siteId: string) =>
  ids.has(jobId) || ids.has(siteId);

export function CrewCalendar({
  scenario,
  plan,
  selected,
  title = "Crew calendar",
  notice,
  highlightedJobIds = [],
  lostCrewDays = [],
  ghosts = [],
  changedJobIds = [],
  arcJobIds = [],
  focusDate,
  onSelect,
}: {
  scenario: Scenario;
  plan: Plan | null;
  selected: string | null;
  title?: string;
  notice?: string;
  highlightedJobIds?: string[];
  lostCrewDays?: { crew_id: string; date: string }[];
  ghosts?: GhostSlot[];
  changedJobIds?: string[];
  arcJobIds?: string[];
  focusDate?: string;
  onSelect: (id: string) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [visitArcs, setVisitArcs] = useState<
    { siteId: string; path: string }[]
  >([]);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const workDates = new Set([
    ...scenario.crew_days.map((c) => c.date),
    ...(plan?.crew_days.map((c) => c.date) ?? []),
    ...(plan?.assignments.map((a) => a.date) ?? []),
    ...lostCrewDays.map((c) => c.date),
  ]);
  const allDays = datesBetween(
    scenario.config.planning_start,
    scenario.config.planning_end,
  );
  const workingDays = allDays.filter((day) => workDates.has(day));
  const days = workingDays.length ? workingDays : allDays;
  const crews = [
    ...new Set([
      ...scenario.crew_days.map((c) => c.crew_id),
      ...(plan?.crew_days.map((c) => c.crew_id) ?? []),
    ]),
  ].sort((left, right) => {
    const rank = (crew: string) => {
      const skills = [...scenario.crew_days, ...(plan?.crew_days ?? [])]
        .filter((day) => day.crew_id === crew)
        .flatMap((day) => ("skills" in day ? day.skills : []));
      return skills.includes("install")
        ? 0
        : skills.includes("battery")
          ? 1
          : 2;
    };
    return rank(left) - rank(right) || left.localeCompare(right);
  });
  const changed = new Set(changedJobIds);
  const arcFocus = new Set(arcJobIds);
  const isLost = (crew: string, day: string) =>
    lostCrewDays.some((lost) => lost.crew_id === crew && lost.date === day);
  const arcKey = `${selected}|${[...arcFocus].sort().join(",")}`;
  useLayoutEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    const updateArcs = () => {
      const bounds = container.getBoundingClientRect();
      const visits = new Map(
        Array.from(container.querySelectorAll<HTMLElement>("[data-job-id]"))
          .filter((element) => element.dataset.jobId)
          .map((element) => [element.dataset.jobId!, element]),
      );
      const arcs = scenario.sites.flatMap((site) => {
        const install = site.visits?.find(
          (visit) => visit.visit_type === "install",
        );
        const battery = site.visits?.find(
          (visit) => visit.visit_type === "battery_day",
        );
        if (!install || !battery) return [];
        const shown =
          selected === site.site_id ||
          arcFocus.has(install.job_id) ||
          arcFocus.has(battery.job_id);
        const from = visits.get(install.job_id);
        const to = visits.get(battery.job_id);
        if (!shown || !from || !to) return [];
        const start = from.getBoundingClientRect();
        const end = to.getBoundingClientRect();
        const x1 = start.right - bounds.left + container.scrollLeft;
        const y1 =
          start.top + start.height / 2 - bounds.top + container.scrollTop;
        const x2 = end.left - bounds.left + container.scrollLeft;
        const y2 = end.top + end.height / 2 - bounds.top + container.scrollTop;
        const bend = Math.max(24, (x2 - x1) / 2);
        return [
          {
            siteId: site.site_id,
            path: `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`,
          },
        ];
      });
      setVisitArcs(arcs);
      setCanvasSize({
        width: container.scrollWidth,
        height: container.scrollHeight,
      });
    };
    updateArcs();
    const observer = new ResizeObserver(updateArcs);
    observer.observe(container);
    const table = container.querySelector("table");
    if (table) observer.observe(table);
    return () => observer.disconnect();
  }, [scenario, plan, arcKey]);
  const focusColumn = focusDate
    ? (days.find((day) => day >= weekStart(focusDate) && day <= focusDate) ??
      focusDate)
    : undefined;
  useLayoutEffect(() => {
    const container = scrollRef.current;
    if (!container || !focusColumn) return;
    const column = container.querySelector<HTMLElement>(
      `thead th[data-date="${focusColumn}"]`,
    );
    const label = container.querySelector<HTMLElement>("thead th");
    if (!column || !label) return;
    const offset =
      column.getBoundingClientRect().left -
      container.getBoundingClientRect().left +
      container.scrollLeft -
      label.getBoundingClientRect().width;
    container.scrollLeft = Math.max(0, offset);
  }, [focusColumn, scenario]);
  return (
    <section className="panel calendar" data-testid="plan-lanes">
      <div className="panel-heading">
        <h2>{title}</h2>
        <span>{crews.length} crews · daily capacity, not arrival times</span>
      </div>
      {notice && (
        <p className="calendar-notice" role="status">
          {notice}
        </p>
      )}
      <div className="table-scroll" ref={scrollRef}>
        <table>
          <thead>
            <tr>
              <th>Crew / cluster</th>
              {days.map((d) => (
                <th
                  key={d}
                  data-date={d}
                  className={d === focusDate ? "focus-day" : undefined}
                >
                  <span className="mono">{dateLabel(d)}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {crews.map((crew) => (
              <tr key={crew}>
                <th>
                  <strong>Crew {crew}</strong>
                  <small>
                    {[
                      ...new Set(
                        [...scenario.crew_days, ...(plan?.crew_days ?? [])]
                          .filter((c) => c.crew_id === crew)
                          .flatMap((c) =>
                            "allowed_clusters" in c ? c.allowed_clusters : [],
                          ),
                      ),
                    ].join(" / ")}
                  </small>
                </th>
                {days.map((day) => {
                  const usage = plan?.crew_days.find(
                    (c) => c.crew_id === crew && c.date === day,
                  );
                  const capacity = usage?.available_min ?? 0;
                  const lost = isLost(crew, day);
                  const jobs =
                    plan?.assignments.filter(
                      (a) => a.crew_id === crew && a.date === day,
                    ) ?? [];
                  const cellGhosts = ghosts.filter(
                    (ghost) =>
                      ghost.crew_id === crew &&
                      ghost.date === day &&
                      !jobs.some(
                        (job) => (job.job_id ?? job.site_id) === ghost.job_id,
                      ),
                  );
                  const busy =
                    (usage?.onsite_min ?? 0) + (usage?.travel_min ?? 0);
                  return (
                    <td
                      key={day}
                      data-testid={
                        lost ? `lost-capacity-${crew}-${day}` : undefined
                      }
                      className={`${!capacity ? "unavailable" : ""} ${
                        lost ? "lost-capacity" : ""
                      }`}
                    >
                      <div className="cell-meta">
                        <span>
                          {capacity
                            ? `${busy} / ${capacity} min`
                            : lost
                              ? "Unavailable · modeled disruption"
                              : "Unavailable"}
                        </span>
                        <span>{usage?.cluster_id ?? "—"}</span>
                      </div>
                      {capacity > 0 && (
                        <div
                          className="capacity"
                          role="meter"
                          aria-label={`Crew ${crew} ${day} capacity`}
                          aria-valuenow={busy}
                          aria-valuemax={capacity}
                          aria-valuemin={0}
                        >
                          <span
                            style={{
                              width: `${Math.min(100, (busy / capacity) * 100)}%`,
                            }}
                          />
                        </div>
                      )}
                      <div className="jobs">
                        {jobs.map((a) => {
                          const jobId = a.job_id ?? a.site_id;
                          const site = scenario.sites.find(
                            (s) => s.site_id === a.site_id,
                          );
                          const visit = site?.visits?.find(
                            (v) => v.job_id === a.job_id,
                          );
                          const visitLabel =
                            a.visit_type === "install"
                              ? "Install"
                              : a.visit_type === "battery_day"
                                ? "Battery day"
                                : null;
                          const highlighted = highlightedJobIds.some(
                            (id) =>
                              id === a.job_id ||
                              id === a.site_id ||
                              a.job_id?.startsWith(`${id}-`),
                          );
                          const moved = matchesJob(changed, jobId, a.site_id);
                          return (
                            <button
                              key={jobId}
                              data-job-id={a.job_id ?? undefined}
                              aria-pressed={selected === a.site_id}
                              data-testid={`visit-${jobId}`}
                              className={`job ${selected === a.site_id ? "selected" : ""} ${highlighted ? "highlighted" : ""} ${changedJobIds.length ? (moved ? "moved-visit" : "unchanged-visit") : ""}`}
                              onClick={() => onSelect(a.site_id)}
                            >
                              <div>
                                <strong className="mono">{a.site_id}</strong>
                                <Status state={a.state} days={a.days_late} />
                              </div>
                              <small>
                                {visitLabel ? `${visitLabel} · ` : ""}
                                {visit?.duration_min ?? site?.duration_min} min
                                on-site
                              </small>
                            </button>
                          );
                        })}
                        {cellGhosts.map((ghost) => (
                          <div
                            key={`ghost-${ghost.job_id}`}
                            className="job moved-ghost"
                            data-testid={`ghost-${ghost.job_id}`}
                          >
                            <div>
                              <strong className="mono">{ghost.site_id}</strong>
                              <span>
                                {ghost.kind === "removed"
                                  ? "Unscheduled"
                                  : "Moved"}
                              </span>
                            </div>
                          </div>
                        ))}
                        {plan &&
                          capacity > 0 &&
                          !jobs.length &&
                          !cellGhosts.length && (
                            <span className="empty">No visits planned</span>
                          )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {visitArcs.length > 0 && (
          <svg
            className="visit-arcs"
            width={canvasSize.width}
            height={canvasSize.height}
            aria-hidden="true"
          >
            <defs>
              <marker
                id="visit-arc-arrow"
                markerWidth="6"
                markerHeight="6"
                refX="5"
                refY="3"
                orient="auto"
              >
                <path d="M0,0 L6,3 L0,6 z" />
              </marker>
            </defs>
            {visitArcs.map((arc) => (
              <path
                key={arc.siteId}
                data-testid="visit-arc"
                d={arc.path}
                markerEnd="url(#visit-arc-arrow)"
              />
            ))}
          </svg>
        )}
      </div>
    </section>
  );
}

function weekStart(date: string) {
  const day = new Date(`${date}T12:00:00Z`);
  const offset = (day.getUTCDay() + 6) % 7;
  day.setUTCDate(day.getUTCDate() - offset);
  return day.toISOString().slice(0, 10);
}
