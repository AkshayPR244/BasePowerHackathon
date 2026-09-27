import reports from "./reports.json";
export interface Narrative {
  scenario_id: string;
  title: string;
  operator: string;
  situation: string;
  trigger: string;
  question: string;
  what_to_watch: string[];
  success_criterion: string;
  truth_label: string;
}
// Frontend-only editorial metadata. Never sent to any API endpoint.
export const narratives: Record<string, Narrative> = reports;
export const narrativeFor = (id: string): Narrative | undefined =>
  narratives[id];
