import { expect, test } from "vitest";
import { planCsv } from "./export";
import fixture from "../mocks/recorded/plan_tiny_recovery_remove_a_mon.json";
import type { Plan } from "../api/types";
test("exports assignments, missed commitments, assumptions and solver status", () => {
  const csv = planCsv(fixture as Plan);
  for (const text of [
    "assignment",
    "missed_commitment",
    "assumption",
    "solver",
    "validation",
    "Not validated",
    "N-02",
    "S-03",
  ])
    expect(csv).toContain(text);
});
test("quotes delimiters and prevents spreadsheet formulas", () => {
  const plan = structuredClone(fixture) as Plan;
  plan.message = '=SUM(1,2) "test"';
  expect(planCsv(plan)).toContain(`"'=SUM(1,2) ""test"""`);
});
