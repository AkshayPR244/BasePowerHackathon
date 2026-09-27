import { create } from "zustand";
import type { Edit, Plan } from "../api/types";
interface State {
  scenarioId: string;
  revision: number;
  session: number;
  edits: Edit[];
  selected: string | null;
  result: Plan | null;
  baseline: Plan | null;
  select: (id: string | null) => void;
  edit: (edit: Edit) => void;
  replaceEdits: (edits: Edit[]) => void;
  accept: (plan: Plan) => boolean;
  reset: (scenarioId?: string) => void;
}
export const defaultScenarioId = "standard";
function initialScenarioId() {
  try {
    return (
      new URLSearchParams(globalThis.location?.search ?? "").get("scenario") ??
      defaultScenarioId
    );
  } catch {
    return defaultScenarioId;
  }
}
export const useWorkspace = create<State>((set, get) => ({
  scenarioId: initialScenarioId(),
  revision: 0,
  session: 0,
  edits: [],
  selected: null,
  result: null,
  baseline: null,
  select: (selected) => set({ selected }),
  edit: (edit) =>
    set((s) => ({ edits: [...s.edits, edit], revision: s.revision + 1 })),
  replaceEdits: (edits) => set((s) => ({ edits, revision: s.revision + 1 })),
  accept: (plan) => {
    const s = get();
    if (plan.revision !== s.revision || plan.scenario_id !== s.scenarioId)
      return false;
    set({
      result: plan,
      baseline: s.baseline ?? (plan.objective ? structuredClone(plan) : null),
    });
    return true;
  },
  reset: (scenarioId) =>
    set((s) => ({
      scenarioId: scenarioId ?? s.scenarioId,
      revision: s.revision + 1,
      session: s.session + 1,
      edits: [],
      selected: null,
      result: null,
      baseline: null,
    })),
}));
