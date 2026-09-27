import { describe, expect, it } from "vitest";
import type { Schema } from "../api/types";
import { currentPlanForProtection } from "./LiveRecoveryCanvas";

type PlannedInstall = Schema["PlannedInstall"];
type Disruption = Schema["RecoveryOptionsRequest"]["disruption"];

const rows: PlannedInstall[] = [
  {
    crew_id: "IA",
    date: "2018-06-04",
    job_id: "N-01-install",
    locked: true,
    site_id: "N-01",
  },
  {
    crew_id: "IB",
    date: "2018-06-04",
    job_id: "S-04-install",
    locked: true,
    site_id: "S-04",
  },
];

const plan = (disruption: Disruption, protectedHomes: string[] = []) =>
  currentPlanForProtection(rows, protectedHomes, disruption);

describe("currentPlanForProtection", () => {
  it("keeps baseline locks without a disruption", () => {
    expect(plan([]).map((row) => row.locked)).toEqual([true, true]);
  });

  it.each(["remove_crew_day", "reduce_crew_day"] as const)(
    "%s unlocks the affected crew-day only",
    (kind) => {
      const edit =
        kind === "remove_crew_day"
          ? { kind, crew_id: "IA", date: "2018-06-04" }
          : {
              kind,
              crew_id: "IA",
              date: "2018-06-04",
              available_min: 240,
            };
      expect(plan([edit]).map((row) => row.locked)).toEqual([false, true]);
    },
  );

  it("change_appointment unlocks only the named job", () => {
    expect(
      plan([
        {
          kind: "change_appointment",
          job_id: "N-01-install",
          available_from: "2018-06-05",
        },
      ]).map((row) => row.locked),
    ).toEqual([false, true]);
  });

  it("keeps a protected home locked through a disruption", () => {
    expect(
      plan(
        [
          {
            kind: "change_appointment",
            job_id: "N-01-install",
            available_from: "2018-06-05",
          },
        ],
        ["N-01"],
      )[0].locked,
    ).toBe(true);
  });
});
