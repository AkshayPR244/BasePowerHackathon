import { afterAll, beforeAll, expect, test } from "vitest";
import { setupServer } from "msw/node";
import { handlers } from "./handlers";
import index from "./recorded/index.json";
const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());
for (const entry of index)
  test(`serves recording ${entry.name}`, async () => {
    const r = await fetch(`http://localhost${entry.path}`, {
      method: entry.method,
      ...(entry.request
        ? {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(entry.request),
          }
        : {}),
    });
    expect(r.status).toBe(200);
  });
const post = (path: string, body: unknown) =>
  fetch(`http://localhost${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
const recorded = (name: string) =>
  structuredClone(
    index.find((entry) => entry.name === name)!.request,
  ) as Record<string, unknown>;
test("recovery mocks match on disruption, interventions, overrides and option", async () => {
  const options = recorded("recovery_options_standard_storm");
  expect((await post("/api/recovery/options", options)).status).toBe(200);
  expect(
    (
      await post("/api/recovery/options", {
        ...options,
        economics_overrides: {},
      })
    ).status,
  ).toBe(200);
  expect(
    (
      await post("/api/recovery/options", {
        ...options,
        economics_overrides: { hourly_wage: 100 },
      })
    ).status,
  ).toBe(501);
  expect(
    (await post("/api/recovery/options", { ...options, disruption: [] }))
      .status,
  ).toBe(501);
  const evaluate = recorded("recovery_evaluate_standard_storm");
  expect((await post("/api/recovery/evaluate", evaluate)).status).toBe(200);
  const overtime = await post("/api/recovery/evaluate", {
    ...evaluate,
    interventions: [
      {
        kind: "extend_crew_day",
        crew_id: "BA",
        date: "2018-06-15",
        extra_min: 120,
      },
    ],
  });
  expect(overtime.status).toBe(501);
  expect((await overtime.json()).code).toBe("mock_not_recorded");
  const approve = recorded("recovery_approve_standard_storm");
  const option = approve.option as Record<string, unknown>;
  expect(
    (
      await post("/api/recovery/approve", {
        ...approve,
        option: { ...option, option_id: "no_action-other" },
      })
    ).status,
  ).toBe(501);
});
test("echoes client revision and rejects unsupported edits", async () => {
  const body = { scenario_id: "tiny", revision: 19, mode: "strict", edits: [] };
  const r = await fetch("http://localhost/api/plans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  expect((await r.json()).revision).toBe(19);
  const missing = await fetch("http://localhost/api/plans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, algorithm: "baseline_edf" }),
  });
  expect(missing.status).toBe(501);
});
