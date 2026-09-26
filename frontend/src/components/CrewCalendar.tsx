import type { Plan, Scenario } from "../api/types";
import { datesBetween, dateLabel } from "../lib/format";
import { Status } from "../design/status";
export function CrewCalendar({
  scenario,
  plan,
  selected,
  onSelect,
}: {
  scenario: Scenario;
  plan: Plan | null;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const days = datesBetween(
    scenario.config.planning_start,
    scenario.config.planning_end,
  );
  const crews = [
    ...new Set([
      ...scenario.crew_days.map((c) => c.crew_id),
      ...(plan?.crew_days.map((c) => c.crew_id) ?? []),
    ]),
  ].sort();
  return (
    <section className="panel calendar">
      <div className="panel-heading">
        <h2>Crew calendar</h2>
        <span>{crews.length} crews · daily capacity, not arrival times</span>
      </div>
      <div className="table-scroll">
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
                  const busy =
                    (usage?.onsite_min ?? 0) + (usage?.travel_min ?? 0);
                  return (
                    <td key={day} className={!capacity ? "unavailable" : ""}>
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
                            {jobs.map((a) => (
                              <button
                                key={a.site_id}
                                aria-pressed={selected === a.site_id}
                                className={`job ${selected === a.site_id ? "selected" : ""}`}
                                onClick={() => onSelect(a.site_id)}
                              >
                                <div>
                                  <strong className="mono">{a.site_id}</strong>
                                  <Status state={a.state} days={a.days_late} />
                                </div>
                                <small>
                                  {
                                    scenario.sites.find(
                                      (s) => s.site_id === a.site_id,
                                    )?.duration_min
                                  }{" "}
                                  min on-site
                                </small>
                              </button>
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
      </div>
    </section>
  );
}
