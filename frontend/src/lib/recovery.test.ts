import { expect, test } from "vitest";
import type { Scenario } from "../api/types";
import standard from "../mocks/recorded/scenario_standard.json";
import tiny from "../mocks/recorded/scenario_tiny.json";
import options from "../mocks/recorded/recovery_options_standard_storm.json";
import {
  describeDisruption,
  earliestDate,
  hasValidPlan,
  parseOverride,
  recoveryCases,
  slotsOffPlan,
  statusLabel,
  temporaryCrewId,
  type Option,
} from "./recovery";

const scenario = standard as unknown as Scenario;
const rebalance = options.options[0] as unknown as Option;

test("describes the analyzed disruption from its edits", () => {
  expect(describeDisruption(recoveryCases.standard, scenario)).toBe(
    "Modeled disruption: all field crews unavailable Thu 14 Jun.",
  );
  expect(
    describeDisruption(
      [{ kind: "remove_crew_day", crew_id: "IB", date: "2018-06-13" }],
      scenario,
    ),
  ).toBe("Modeled disruption: Crew IB unavailable Wed 13 Jun.");
  expect(earliestDate(recoveryCases.standard)).toBe("2018-06-14");
});

test("approves and draws only validated plans with a solution", () => {
  expect(hasValidPlan(rebalance)).toBe(true);
  expect(hasValidPlan({ ...rebalance, status: "timeout_no_incumbent" })).toBe(
    false,
  );
  expect(
    hasValidPlan({
      ...rebalance,
      result: {
        ...rebalance.result,
        validation: { ...rebalance.result.validation, valid: false },
      },
    }),
  ).toBe(false);
  expect(
    hasValidPlan({
      ...rebalance,
      result: {
        ...rebalance.result,
        validation: { ...rebalance.result.validation, checked: false },
      },
    }),
  ).toBe(false);
  expect(
    statusLabel({ ...rebalance, status: "feasible", proven_optimal: false }),
  ).toBe("Best found, not proven");
});

test("treats empty and negative assumption input as invalid", () => {
  expect(parseOverride("")).toBeNull();
  expect(parseOverride("  ")).toBeNull();
  expect(parseOverride("-1")).toBeNull();
  expect(parseOverride("abc")).toBeNull();
  expect(parseOverride("0")).toBe(0);
  expect(parseOverride("28.5")).toBe(28.5);
});

test("names a temporary crew that does not collide with real crews", () => {
  expect(temporaryCrewId(tiny as unknown as Scenario)).toBe("C");
  expect(temporaryCrewId(scenario)).toBe("TEMP-1");
});

test("lists previous slots for visits moved off the disruption day", () => {
  const slots = slotsOffPlan(rebalance);
  expect(slots.some((slot) => slot.date === "2018-06-14")).toBe(true);
  expect(slots.every((slot) => slot.crew_id && slot.date)).toBe(true);
});
