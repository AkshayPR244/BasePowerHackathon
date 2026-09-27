import type { Edit } from "../api/types";
export interface Preset {
  scenario_id: string;
  seed: number;
  primary_disruption: Edit[];
  recovery_class: string;
}
const files = import.meta.glob("./*.json", {
  eager: true,
  import: "default",
}) as Record<string, Preset>;
const presets = Object.fromEntries(
  Object.values(files).map((p) => [p.scenario_id, p]),
);
export const presetFor = (id: string): Preset | undefined => presets[id];
