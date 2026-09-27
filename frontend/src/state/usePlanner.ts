import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../api/client";
import type { Edit, Mode, Schema } from "../api/types";
import { useWorkspace } from "./store";
import { temporaryCrewId } from "../lib/recovery";
export function usePlanner() {
  const state = useWorkspace(),
    { scenarioId, revision, edits, result, baseline, selected } = state;
  const [busy, setBusy] = useState(""),
    [error, setError] = useState("");
  const [diff, setDiff] = useState<Schema["PlanDiff"] | null>(null),
    [cf, setCf] = useState<Schema["CounterfactualResult"] | null>(null);
  const requestId = useRef(0);
  const scenarios = useQuery({
    queryKey: ["scenarios"],
    queryFn: async () => unwrap(await api.GET("/api/scenarios")),
  });
  const scenario = useQuery({
    queryKey: ["scenario", scenarioId],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/scenarios/{scenario_id}", {
          params: { path: { scenario_id: scenarioId } },
        }),
      ),
  });
  const stale = !!result && result.revision !== revision;
  const validShape =
    !!result?.objective &&
    !(result.validation.checked && !result.validation.valid);
  const invalidate = () => {
    requestId.current++;
    setBusy("");
    setError("");
    setDiff(null);
    setCf(null);
  };
  const solve = async (mode: Mode) => {
    const id = ++requestId.current;
    setBusy(`Solving ${mode} plan…`);
    setError("");
    setDiff(null);
    setCf(null);
    try {
      const response = unwrap(
        await api.POST("/api/plans", {
          body: {
            algorithm: "cpsat",
            scenario_id: scenarioId,
            revision,
            mode,
            edits,
          },
        }),
      );
      if (id === requestId.current) state.accept(response);
    } catch (e) {
      if (id === requestId.current) setError((e as Error).message);
    } finally {
      if (id === requestId.current) setBusy("");
    }
  };
  // One strict solve per scenario revision, also under StrictMode's double effects.
  const autoSolved = useRef("");
  useEffect(() => {
    if (
      !scenario.data ||
      scenario.data.scenario_id !== scenarioId ||
      useWorkspace.getState().result
    )
      return;
    const key = `${scenarioId}:${revision}`;
    if (autoSolved.current === key) return;
    autoSolved.current = key;
    void solve("strict");
  }, [scenario.data, scenarioId, revision]);
  const reset = (id?: string) => {
    invalidate();
    state.reset(id);
  };
  const edit = (value: Edit) => {
    invalidate();
    state.edit(value);
  };
  const compare = async () => {
    if (!baseline || !result || stale) return;
    const id = ++requestId.current;
    setBusy("Comparing plans…");
    setError("");
    try {
      const value = unwrap(
        await api.POST("/api/plans/compare", {
          body: { before: baseline, after: result },
        }),
      );
      if (id === requestId.current) setDiff(value);
    } catch (e) {
      if (id === requestId.current) setError((e as Error).message);
    } finally {
      if (id === requestId.current) setBusy("");
    }
  };
  const intervention = async (kind: "force" | "crew") => {
    if (!result || !selected || !scenario.data || stale) return;
    const site = scenario.data.sites.find((s) => s.site_id === selected);
    const input: Edit =
      kind === "force"
        ? { kind: "force_include", site_id: selected }
        : {
            kind: "add_crew_day",
            crew_id: temporaryCrewId(scenario.data),
            date: scenario.data.config.planning_start,
            available_min: 480,
            skills: [
              site?.required_skill ??
                scenario.data.crew_days[0]?.skills[0] ??
                "install",
            ],
            allowed_clusters: [
              site?.cluster_id ?? scenario.data.clusters[0]?.cluster_id ?? "",
            ],
          };
    const id = ++requestId.current;
    setBusy("Testing intervention…");
    setError("");
    setCf(null);
    try {
      const value = unwrap(
        await api.POST("/api/plans/counterfactual", {
          body: {
            request: {
              algorithm: "cpsat",
              scenario_id: scenarioId,
              revision,
              mode: result.mode,
              edits,
            },
            base: result,
            intervention: input,
          },
        }),
      );
      if (
        id === requestId.current &&
        useWorkspace.getState().selected === selected
      )
        setCf(value);
    } catch (e) {
      if (id === requestId.current) setError((e as Error).message);
    } finally {
      if (id === requestId.current) setBusy("");
    }
  };
  useEffect(() => {
    setCf(null);
  }, [selected]);
  return {
    state,
    scenarioId,
    revision,
    edits,
    result,
    baseline,
    selected,
    busy,
    error,
    diff,
    cf,
    scenarios,
    scenario,
    stale,
    validShape,
    solve,
    reset,
    edit,
    compare,
    intervention,
  };
}
