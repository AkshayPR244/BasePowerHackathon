import type { components } from "./generated";
export type Schema = components["schemas"];
export type Plan = Schema["PlanResult"];
export type Scenario = Schema["Scenario"];
export type Edit = NonNullable<Schema["PlanRequest"]["edits"]>[number];
export type Mode = Schema["Mode"];
