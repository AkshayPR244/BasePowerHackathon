import { useLayoutEffect, useRef, useState } from "react";
import type { Plan, Scenario } from "../api/types";
import { datesBetween, dateLabel } from "../lib/format";
import { Status } from "../design/status";
export function CrewCalendar({
  scenario,
  plan,
  selected,
  highlightedJobIds = [],
  lostCrewDays = [],
  beforeAssignments = [],
  changedJobIds = [],
  onSelect,
}: {
  scenario: Scenario;
  plan: Plan | null;
  selected: string | null;
  highlightedJobIds?: string[];
  lostCrewDays?: { crew_id: string; date: string }[];
  beforeAssignments?: Plan["assignments"];
  changedJobIds?: string[];
  onSelect: (id: string) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [visitArcs, setVisitArcs] = useState<
    { siteId: string; path: string }[]
  >([]);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const days = datesBetween(
    scenario.config.planning_start,
    scenario.config.planning_end,
  );
  const crews = [
    ...new Set([
      ...scenario.crew_days.map((c) => c.crew_id),
      ...(plan?.crew_days.map((c) => c.crew_id) ?? []),
    ]),
  ].sort((left, right) => {
    const rank = (crew: string) => {
      const skills = scenario.crew_days
        .filter((day) => day.crew_id === crew)
        .flatMap((day) => day.skills);
      return skills.includes("install")
        ? 0
        : skills.includes("battery")
          ? 1
          : 2;
    };
    return rank(left) - rank(right) || left.localeCompare(right);
  });
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
        const from = install && visits.get(install.job_id);
        const to = battery && visits.get(battery.job_id);
        if (!from || !to) return [];
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
  }, [scenario, plan]);
  return (
    <section className="panel calendar">
      <div className="panel-heading">
        <h2>Crew calendar</h2>
        <span>{crews.length} crews · daily capacity, not arrival times</span>
      </div>
      <div className="table-scroll" ref={scrollRef}>
        <table>
          <thead>
            <tr>
              <th>Crew / cluster</th>
              {days.map((d) => (
                <th key={d}>{dateLabel(d)}</th>
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
                        scenario.crew_days
                          .filter((c) => c.crew_id === crew)
                          .flatMap((c) => c.allowed_clusters),
                      ),
                    ].join(" / ")}
                  </small>
                </th>
                {days.map((day) => {
                  const usage = plan?.crew_days.find(
                    (c) => c.crew_id === crew && c.date === day,
                  );
                  const capacity = usage?.available_min ?? 0;
                  const jobs =
                    plan?.assignments.filter(
                      (a) => a.crew_id === crew && a.date === day,
                    ) ?? [];
                  const ghosted = beforeAssignments.filter(
                    (assignment) =>
                      changedJobIds.includes(
                        assignment.job_id ?? assignment.site_id,
                      ) &&
                      assignment.crew_id === crew &&
                      assignment.date === day &&
                      !jobs.some(
                        (job) =>
                          (job.job_id ?? job.site_id) ===
                          (assignment.job_id ?? assignment.site_id),
                      ),
                  );
                  const busy =
                    (usage?.onsite_min ?? 0) + (usage?.travel_min ?? 0);
                  return (
                    <td
                      key={day}
                      data-testid={
                        lostCrewDays.some(
                          (lost) => lost.crew_id === crew && lost.date === day,
                        )
                          ? `lost-capacity-${crew}-${day}`
                          : undefined
                      }
                      className={`${!capacity ? "unavailable" : ""} ${
                        lostCrewDays.some(
                          (lost) => lost.crew_id === crew && lost.date === day,
                        )
                          ? "lost-capacity"
                          : ""
                      }`}
                    >
                      <div className="cell-meta">
                        <span>
                          {capacity
                            ? `${busy} / ${capacity} min`
                            : "Unavailable"}
                        </span>
                        <span>{usage?.cluster_id ?? "—"}</span>
                      </div>
                      {capacity > 0 && (
                        <>
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
                          <div className="jobs">
                            {jobs.map((a) => {
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
                              const changed = changedJobIds.includes(
                                a.job_id ?? a.site_id,
                              );
                              return (
                                <button
                                  key={a.job_id ?? a.site_id}
                                  data-job-id={a.job_id ?? undefined}
                                  aria-pressed={selected === a.site_id}
                                  data-testid={`visit-${a.job_id ?? a.site_id}`}
                                  className={`job ${selected === a.site_id ? "selected" : ""} ${highlighted ? "highlighted" : ""} ${changed ? "moved-visit" : "unchanged-visit"}`}
                                  onClick={() => onSelect(a.site_id)}
                                >
                                  <div>
                                    <strong className="mono">
                                      {a.site_id}
                                    </strong>
                                    <Status
                                      state={a.state}
                                      days={a.days_late}
                                    />
                                  </div>
                                  <small>
                                    {visitLabel ? `${visitLabel} · ` : ""}
                                    {visit?.duration_min ??
                                      site?.duration_min}{" "}
                                    min on-site
                                  </small>
                                </button>
                              );
                            })}
                            {ghosted.map((a) => (
                              <div
                                key={`ghost-${a.job_id ?? a.site_id}`}
                                className="job moved-ghost"
                                data-testid={`ghost-${a.job_id ?? a.site_id}`}
                              >
                                <div>
                                  <strong className="mono">{a.site_id}</strong>
                                  <span>Moved</span>
                                </div>
                                <small>Previous crew-day</small>
                              </div>
                            ))}
                            {!jobs.length && (
                              <span className="empty">No installs planned</span>
                            )}
                          </div>
                        </>
                      )}
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
