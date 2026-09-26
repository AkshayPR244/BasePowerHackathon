import { http, HttpResponse, delay } from "msw";
import index from "./recorded/index.json";
const files = import.meta.glob("./recorded/*.json", {
  eager: true,
  import: "default",
}) as Record<string, unknown>;
// Ignore transport metadata, but never match a different plan, edit, or intervention.
export function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.entries(value)
      .filter(([k]) => !["revision", "solve_ms", "elapsed_ms"].includes(k))
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${JSON.stringify(k)}:${canonical(v)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}
function normalize(value: unknown): unknown {
  if (!value || typeof value !== "object" || Array.isArray(value)) return value;
  const v = value as Record<string, unknown>;
  if ("scenario_id" in v && !("plan_id" in v))
    return {
      scenario_id: v.scenario_id,
      mode: v.mode ?? "strict",
      edits: v.edits ?? [],
      algorithm: v.algorithm ?? "cpsat",
      objective_policy: v.objective_policy ?? null,
    };
  if ("before" in v)
    return { before: normalize(v.before), after: normalize(v.after) };
  if ("base" in v)
    return {
      request: normalize(v.request),
      base: normalize(v.base),
      intervention: v.intervention,
    };
  return value;
}
export const handlers = ["GET", "POST"].map((method) =>
  (method === "GET" ? http.get : http.post)("*/api/*", async ({ request }) => {
    const path = new URL(request.url).pathname;
    const body =
      method === "POST"
        ? ((await request.json()) as Record<string, unknown>)
        : null;
    const entry = index.find(
      (e) =>
        e.method === method &&
        e.path === path &&
        canonical(normalize(e.request)) === canonical(normalize(body)),
    );
    if (!entry)
      return HttpResponse.json(
        {
          code: "mock_not_recorded",
          message:
            "This request has no recorded response. Reset the demo or use the live API.",
          input_issues: [],
        },
        { status: 501 },
      );
    await delay(150);
    const data = structuredClone(
      files[`./recorded/${entry.name}.json`],
    ) as Record<string, unknown>;
    if (path === "/api/plans" && body) data.revision = body.revision;
    if (path.endsWith("/counterfactual") && body) {
      (data.result as Record<string, unknown>).revision = (
        body.request as Record<string, unknown>
      ).revision;
    }
    return HttpResponse.json(data);
  }),
);
