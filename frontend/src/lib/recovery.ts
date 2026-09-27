import type { Scenario, Schema } from "../api/types";
import { dateLabel } from "./format";

export type Disruption = Schema["RecoveryOptionsRequest"]["disruption"][number];
export type Intervention = Schema["EvaluateRequest"]["interventions"][number];
export type Option = Schema["RecoveryOption"];

// The known disruption the canvas analyzes for each scenario.
export const recoveryCases: Record<string, Disruption[]> = {
  standard: [
    { kind: "remove_crew_day", crew_id: "IA", date: "2018-06-14" },
    { kind: "remove_crew_day", crew_id: "IB", date: "2018-06-14" },
    { kind: "remove_crew_day", crew_id: "BA", date: "2018-06-14" },
  ],
};

const dated = (edit: Disruption): edit is Disruption & { date: string } =>
  "date" in edit && typeof edit.date === "string";

export function earliestDate(disruption: Disruption[]): string | undefined {
  return disruption
    .filter(dated)
    .map((edit) => edit.date)
    .sort()[0];
}

const joinNames = (names: string[]) =>
  names.length <= 1
    ? (names[0] ?? "")
    : `${names.slice(0, -1).join(", ")} and ${names.at(-1)}`;

export function describeDisruption(
  disruption: Disruption[],
  scenario: Scenario,
): string {
  const parts: string[] = [];
  const removedByDate = new Map<string, string[]>();
  for (const edit of disruption)
    if (edit.kind === "remove_crew_day")
      removedByDate.set(edit.date, [
        ...(removedByDate.get(edit.date) ?? []),
        edit.crew_id,
      ]);
  for (const [date, crews] of [...removedByDate].sort()) {
    const working = new Set(
      scenario.crew_days.filter((c) => c.date === date).map((c) => c.crew_id),
    );
    const all =
      working.size > 0 && [...working].every((crew) => crews.includes(crew));
    parts.push(
      all
        ? `all field crews unavailable ${dateLabel(date)}`
        : `${joinNames([...new Set(crews)].sort().map((c) => `Crew ${c}`))} unavailable ${dateLabel(date)}`,
    );
  }
  for (const edit of disruption) {
    if (edit.kind === "reduce_crew_day")
      parts.push(
        `Crew ${edit.crew_id} limited to ${edit.available_min} min ${dateLabel(edit.date)}`,
      );
    else if (edit.kind === "delay_inventory")
      parts.push(
        `a battery delivery moves from ${dateLabel(edit.from_date)} to ${dateLabel(edit.to_date)}`,
      );
    else if (edit.kind === "change_ready_date")
      parts.push(`${edit.site_id} is ready ${dateLabel(edit.ready_date)}`);
  }
  if (!parts.length)
    return `Modeled disruption: ${disruption.length} operational ${disruption.length === 1 ? "change" : "changes"}.`;
  const text = joinNames(parts);
  return `Modeled disruption: ${text}.`;
}

export function statusLabel(option: Option): string {
  switch (option.status) {
    case "optimal":
      return "Optimal";
    case "feasible":
      return option.proven_optimal || option.kind === "no_action"
        ? "Feasible"
        : "Best found, not proven";
    case "infeasible":
      return "Infeasible";
    case "timeout_no_incumbent":
      return "Timed out (no plan found)";
    case "invalid_input":
      return "Invalid input";
  }
}

// No action keeps the current plan, so there is no search to prove.
export const unproven = (option: Option) =>
  option.status === "feasible" &&
  !option.proven_optimal &&
  option.kind !== "no_action";

export function validationLabel(option: Option): string {
  const validation = option.result.validation;
  if (!validation.checked) return "Not validated";
  return validation.valid
    ? "Validated"
    : `${validation.issues.length} violations`;
}

// A plan is drawn or approved only when it exists and the independent validator passed it.
export function hasValidPlan(option: Option): boolean {
  return (
    (option.status === "optimal" || option.status === "feasible") &&
    option.result.validation.checked &&
    option.result.validation.valid
  );
}

// Empty, non-numeric, or negative input is invalid, never 0.
export function parseOverride(raw: string): number | null {
  if (raw.trim() === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

export function temporaryCrewId(scenario: Scenario): string {
  const crews = new Set(scenario.crew_days.map((c) => c.crew_id));
  if ([...crews].every((crew) => /^[A-Z]$/.test(crew))) {
    for (let code = 65; code <= 90; code++) {
      const letter = String.fromCharCode(code);
      if (!crews.has(letter)) return letter;
    }
  }
  let n = 1;
  while (crews.has(`TEMP-${n}`)) n++;
  return `TEMP-${n}`;
}

export function slotsOffPlan(option: Option) {
  return option.diff_vs_original.changes.flatMap((change) =>
    change.before && (change.kind === "moved" || change.kind === "removed")
      ? [
          {
            job_id: change.job_id ?? change.site_id,
            site_id: change.site_id,
            crew_id: change.before.crew_id,
            date: change.before.date,
            kind: change.kind,
          },
        ]
      : [],
  );
}
