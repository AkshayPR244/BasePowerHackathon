import { useEffect, useState } from "react";
import { mockMode } from "../api/client";
import { usePlanner } from "../state/usePlanner";
import { useWorkspace } from "../state/store";
import { Header, PlanStatus } from "../components/Header";
import { MetricsStrip } from "../components/MetricsStrip";
import { CrewCalendar } from "../components/CrewCalendar";
import { DeferredList } from "../components/DeferredList";
import { SiteMap } from "../components/SiteMap";
import { Inspector } from "../components/Inspector";
import { EditControls } from "../components/EditControls";
import { ComparePanel } from "../components/ComparePanel";
import { downloadPlan } from "../lib/export";
import { recoveryCases } from "../lib/recovery";
import { RecoveryCanvas } from "./Canvas";
import { useTheme } from "./useTheme";

export function Workspace() {
  const {
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
  } = usePlanner();
  const session = useWorkspace((s) => s.session);
  const { theme, toggleTheme } = useTheme();
  const disruption = recoveryCases[scenarioId];
  const [baselineOpen, setBaselineOpen] = useState<Record<string, boolean>>({});
  const showBaseline = baselineOpen[scenarioId] ?? !disruption;
  useEffect(() => {
    document.title = disruption
      ? "Recovery Canvas · Rollout Planner"
      : "Rollout Planner";
  }, [disruption]);
  if (scenario.isError || scenarios.isError)
    return (
      <main className="startup">
        <h1>Could not load the workspace</h1>
        <p role="alert">{(scenario.error ?? scenarios.error)?.message}</p>
        <button
          onClick={() => {
            void scenario.refetch();
            void scenarios.refetch();
          }}
        >
          Try again
        </button>
      </main>
    );
  if (!scenario.data || scenario.data.scenario_id !== scenarioId)
    return (
      <main className="startup">Loading scenario and crew availability…</main>
    );
  return (
    <main>
      <Header
        scenario={scenario.data}
        scenarios={scenarios.data ?? []}
        onScenario={reset}
        onReset={() => reset()}
        theme={theme}
        onTheme={toggleTheme}
      />
      {disruption ? (
        <RecoveryCanvas
          key={`${scenarioId}:${session}`}
          scenario={scenario.data}
          disruption={disruption}
          mockMode={mockMode}
        />
      ) : (
        <p className="panel padded no-canvas" data-testid="no-recovery-case">
          No disruption is set up for this scenario, so there is no recovery
          analysis. The baseline plan is open below.
        </p>
      )}
      <details
        className="baseline-section"
        data-testid="baseline-section"
        open={showBaseline}
        onToggle={(event) => {
          const open = event.currentTarget.open;
          if (open !== showBaseline)
            setBaselineOpen((current) => ({ ...current, [scenarioId]: open }));
        }}
      >
        <summary>
          <strong>Advanced: baseline plan</strong>
          <span>Strict plan, metrics, site list, map, compare and export</span>
        </summary>
        {showBaseline && (
          <div className="baseline-body">
            <EditControls
              key={scenarioId}
              scenario={scenario.data}
              edits={edits}
              onEdit={edit}
            />
            <div className="workspace-toolbar">
              <div>
                <span className="eyebrow">PLAN / REVISION {revision}</span>
                <strong>
                  {stale
                    ? "Previous result · changes not solved"
                    : result?.mode === "recovery"
                      ? "Recovery plan"
                      : "Strict plan"}
                </strong>
                {result && <PlanStatus plan={result} />}
              </div>
              <div className="actions">
                <button
                  className="primary"
                  disabled={!!busy}
                  onClick={() => void solve("strict")}
                >
                  Solve strict
                </button>
                <button
                  disabled={!!busy || !edits.length}
                  onClick={() => void solve("recovery")}
                >
                  Find recovery
                </button>
                <button
                  disabled={
                    !!busy ||
                    stale ||
                    !validShape ||
                    !baseline ||
                    result?.plan_id === baseline.plan_id
                  }
                  onClick={() => void compare()}
                >
                  Compare plans
                </button>
                <button
                  disabled={!!busy || stale || !validShape}
                  onClick={() => result && downloadPlan(result, "json")}
                >
                  Export JSON
                </button>
                <button
                  disabled={!!busy || stale || !validShape}
                  onClick={() => result && downloadPlan(result, "csv")}
                >
                  Export CSV
                </button>
              </div>
            </div>
            <div aria-live="polite" className="feedback">
              {busy && <p role="status">{busy}</p>}
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              {result && (
                <p className={result.status === "infeasible" ? "warning" : ""}>
                  {result.message}
                </p>
              )}
              {result?.status === "infeasible" && !stale && (
                <p>
                  No plan meets all commitments. Choose “Find recovery” to allow
                  late installs and inspect the trade-offs.
                </p>
              )}
              {result?.validation.checked && !result.validation.valid && (
                <p role="alert" className="error">
                  This result failed validation. Assignments are hidden and
                  export is disabled.
                </p>
              )}
              {result?.input_issues.map((issue, n) => (
                <p key={n} className="error">
                  {issue.message}
                </p>
              ))}
            </div>
            <div
              className={stale ? "result-area stale" : "result-area"}
              aria-busy={!!busy}
            >
              <MetricsStrip plan={validShape ? result : null} />
              <div className="workspace-grid">
                <div className="main-column">
                  <CrewCalendar
                    scenario={scenario.data}
                    plan={validShape ? result : null}
                    selected={selected}
                    onSelect={state.select}
                  />
                  <div className="lower-grid">
                    <SiteMap
                      scenario={scenario.data}
                      plan={validShape ? result : null}
                      noPlanLabel={busy ? "Solving" : "No valid plan"}
                      selected={selected}
                      onSelect={state.select}
                    />
                    <DeferredList plan={result} onSelect={state.select} />
                  </div>
                  {diff && <ComparePanel diff={diff} />}
                </div>
                <Inspector
                  scenario={scenario.data}
                  plan={validShape ? result : null}
                  selected={selected}
                  onIntervention={(kind) => void intervention(kind)}
                  cf={cf}
                  busy={!!busy}
                  canIntervene={
                    !stale &&
                    validShape &&
                    result?.mode === "recovery" &&
                    (!mockMode || selected === "N-02")
                  }
                />
              </div>
            </div>
          </div>
        )}
      </details>
      <footer>
        <span>
          {mockMode
            ? "Recorded API responses · no live optimization"
            : "Live API · computed plans"}{" "}
          · {scenario.data.sites.length} sites
        </span>
        <span>
          Travel is an assumed allowance. Installation inputs are{" "}
          {scenario.data.config.synthetic ? "synthetic" : "source-specific"}.
        </span>
      </footer>
    </main>
  );
}
