import { expect, test } from "vitest";
import {
  primaryHref,
  readSharedRecoveryContext,
  workspaceHref,
} from "./sharedRecoveryContext";

const context = {
  scenarioId: "standard",
  disruption: [
    {
      kind: "remove_crew_day" as const,
      crew_id: "BA",
      date: "2018-06-14",
    },
  ],
  protectedHomes: ["S-02"],
};

test("round-trips the recovery context between both views", () => {
  const workspace = workspaceHref(context);
  expect(workspace).toContain("view=workspace");
  expect(
    readSharedRecoveryContext(workspace.slice(workspace.indexOf("?"))),
  ).toEqual(context);

  const primary = primaryHref(context);
  expect(primary).toContain("view=primary");
  expect(
    readSharedRecoveryContext(primary.slice(primary.indexOf("?"))),
  ).toEqual(context);
});

test("rejects malformed or unknown shared disruptions", () => {
  expect(
    readSharedRecoveryContext("?scenario=standard&disruption=nope"),
  ).toBeNull();
  expect(
    readSharedRecoveryContext(
      `?scenario=standard&disruption=${encodeURIComponent(JSON.stringify([{ kind: "invented" }]))}`,
    ),
  ).toBeNull();
});
