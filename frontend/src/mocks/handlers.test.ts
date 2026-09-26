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
