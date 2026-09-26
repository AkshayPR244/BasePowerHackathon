import type { Plan } from "../api/types";
const quote = (value: unknown) =>
  `"${String(value ?? "")
    .replace(/^[=+@\-]/, "'$&")
    .replaceAll('"', '""')}"`;
export function planCsv(plan: Plan) {
  const rows: unknown[][] = [
    ["record", "site", "crew", "date", "state", "days_late", "detail"],
  ];
  for (const a of plan.assignments)
    rows.push([
      "assignment",
      a.site_id,
      a.crew_id,
      a.date,
      a.state,
      a.days_late,
      "",
    ]);
  for (const u of plan.unscheduled)
    rows.push(["missed_commitment", u.site_id, "", "", u.state, "", u.detail]);
  for (const a of plan.assumptions)
    rows.push(["assumption", "", "", "", a.kind, "", a.text]);
  rows.push(["solver", "", "", "", plan.status, "", plan.message]);
  rows.push([
    "validation",
    "",
    "",
    "",
    plan.validation.checked
      ? plan.validation.valid
        ? "Validated"
        : "Invalid"
      : "Not validated",
    "",
    plan.validation.validator,
  ]);
  return rows.map((r) => r.map(quote).join(",")).join("\r\n");
}
export function downloadPlan(plan: Plan, format: "json" | "csv") {
  const blob = new Blob(
    [format === "json" ? JSON.stringify(plan, null, 2) : planCsv(plan)],
    { type: format === "json" ? "application/json" : "text/csv;charset=utf-8" },
  );
  const url = URL.createObjectURL(blob),
    link = document.createElement("a");
  link.href = url;
  link.download = `${plan.plan_id}.${format}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
