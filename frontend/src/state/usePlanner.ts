import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../api/client";
import type { Edit, Mode, Schema } from "../api/types";
import { useWorkspace } from "./store";
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
  useEffect(() => {
    if (scenario.data && !useWorkspace.getState().result) void solve("strict");
    return () => {
      requestId.current++;
    };
  }, [scenario.data]);
  const reset = (id?: string) => {
    invalidate();
    state.reset(id);
  };
  // Reset on the same scenario needs a fresh solve; scenario data itself is cached.
  useEffect(() => {
    if (scenario.data && !result && !busy) void solve("strict");
  }, [revision]);
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
    const input: Edit =
      kind === "force"
        ? { kind: "force_include", site_id: selected }
        : {
            kind: "add_crew_day",
            crew_id: "C",
            date: scenario.data.config.planning_start,
            available_min: 480,
            skills: [
              scenario.data.sites.find((s) => s.site_id === selected)
                ?.required_skill ?? "install",
            ],
            allowed_clusters: [
              scenario.data.sites.find((s) => s.site_id === selected)
                ?.cluster_id ?? "N",
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
