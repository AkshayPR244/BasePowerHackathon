import type { Schema } from "../api/types";

type Disruption = Schema["RecoveryOptionsRequest"]["disruption"][number];

export interface SharedRecoveryContext {
  scenarioId: string;
  disruption: Disruption[];
  protectedHomes: string[];
}

const disruptionKinds = new Set([
  "remove_crew_day",
  "reduce_crew_day",
  "delay_inventory",
  "change_ready_date",
  "change_appointment",
]);

export function readSharedRecoveryContext(
  search = globalThis.location?.search ?? "",
): SharedRecoveryContext | null {
  try {
    const params = new URLSearchParams(search);
    if (!params.has("disruption")) return null;
    const scenarioId = params.get("scenario")?.trim();
    const parsed = JSON.parse(params.get("disruption") ?? "null");
    const protectedHomes = JSON.parse(params.get("protected") ?? "[]");
    if (
      !scenarioId ||
      !Array.isArray(parsed) ||
      !parsed.every(
        (item) =>
          item &&
          typeof item === "object" &&
          disruptionKinds.has((item as { kind?: string }).kind ?? ""),
      ) ||
      !Array.isArray(protectedHomes) ||
      !protectedHomes.every((id) => typeof id === "string")
    )
      return null;
    return {
      scenarioId,
      disruption: parsed as Disruption[],
      protectedHomes,
    };
  } catch {
    return null;
  }
}

function sharedHref(
  view: "primary" | "workspace",
  context: SharedRecoveryContext,
) {
  const params = new URLSearchParams();
  params.set("view", view);
  params.set("scenario", context.scenarioId);
  params.set("disruption", JSON.stringify(context.disruption));
  if (context.protectedHomes.length)
    params.set("protected", JSON.stringify(context.protectedHomes));
  return `${globalThis.location?.pathname ?? "/"}?${params.toString()}`;
}

export const workspaceHref = (context: SharedRecoveryContext) =>
  sharedHref("workspace", context);

export const primaryHref = (context: SharedRecoveryContext) =>
  sharedHref("primary", context);
