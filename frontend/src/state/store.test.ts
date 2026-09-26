import { beforeEach, expect, test } from "vitest";
import { useWorkspace } from "./store";
import fixture from "../mocks/recorded/plan_tiny_strict.json";
import type { Plan } from "../api/types";
beforeEach(() =>
  useWorkspace.setState({
    scenarioId: "tiny",
    revision: 0,
    edits: [],
    result: null,
    baseline: null,
  }),
);
test("drops stale and different-scenario responses and preserves baseline", () => {
  const initial = structuredClone(fixture) as Plan;
  expect(useWorkspace.getState().accept(initial)).toBe(true);
  useWorkspace
    .getState()
    .edit({ kind: "remove_crew_day", crew_id: "A", date: "2018-06-04" });
  expect(useWorkspace.getState().accept(initial)).toBe(false);
  expect(
    useWorkspace
      .getState()
      .accept({ ...initial, revision: 1, scenario_id: "other" }),
  ).toBe(false);
  expect(
    useWorkspace.getState().accept({ ...initial, revision: 1, plan_id: "new" }),
  ).toBe(true);
  expect(useWorkspace.getState().baseline?.plan_id).toBe(initial.plan_id);
});
