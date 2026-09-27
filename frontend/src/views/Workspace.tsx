import "../design/workspace.css";
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
import { PolicyComparison } from "../components/PolicyComparison";
import { ScenarioBriefing } from "../components/ScenarioBriefing";
import { narrativeFor } from "../narratives";
import { presetFor } from "../scenario-presets";
import { downloadPlan } from "../lib/export";
import {
  describeDisruption,
  disruptionResources,
  recoveryCases,
} from "../lib/recovery";
import {
  primaryHref,
  readSharedRecoveryContext,
} from "../lib/sharedRecoveryContext";
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
    replaceEdits,
    compare,
    intervention,
  } = usePlanner();
  const session = useWorkspace((s) => s.session);
  const { theme, toggleTheme } = useTheme();
  const narrative = narrativeFor(scenarioId);
  const preset = presetFor(scenarioId);
  const sharedContext = readSharedRecoveryContext();
  const shared =
    sharedContext?.scenarioId === scenarioId ? sharedContext : undefined;
  // Suite scenarios analyze the edits the operator applied, or an empty disruption on request.
  const [baselineAnalysis, setBaselineAnalysis] = useState<number | null>(null);
  const suiteActive =
    !!preset && (edits.length > 0 || baselineAnalysis === revision);
  const primaryActive = shared
    ? shared.disruption.length > 0
    : !!preset &&
      (preset.primary_disruption.length === 0
        ? baselineAnalysis === revision
        : JSON.stringify(edits) === JSON.stringify(preset.primary_disruption));
  const disruption =
    shared?.disruption ??
    recoveryCases[scenarioId] ??
    (suiteActive ? edits : undefined);
  useEffect(() => setBaselineAnalysis(null), [scenarioId]);
  const [baselineOpen, setBaselineOpen] = useState<Record<string, boolean>>({});
  const showBaseline = baselineOpen[scenarioId] ?? !disruption;
  useEffect(() => {
    document.title = disruption ? "Recovery Canvas · SlackLine" : "SlackLine";
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
  const sharedCurrentPlan = shared?.protectedHomes.length
    ? scenario.data.current_plan.map((row) => ({
        ...row,
        locked: row.locked || shared.protectedHomes.includes(row.site_id),
      }))
    : undefined;
  const sharedDescription = shared?.disruption.length
    ? describeDisruption(shared.disruption, scenario.data)
    : undefined;
  const sharedBannerCopy = sharedDescription
    ? {
        trigger: sharedDescription,
        whatWentWrong: `The operator applied this modeled change to the working plan: ${sharedDescription.replace(/^Modeled disruption:\s*/i, "")}`,
        unavailableResources: disruptionResources(shared?.disruption ?? []),
        question:
          "Which validated recovery best protects deadlines while limiting customer appointment changes?",
      }
    : undefined;
  const briefingNarrative =
    narrative ??
    (shared
      ? {
          scenario_id: scenarioId,
          title: "Live disruption analysis",
          operator: "Dispatch manager",
          situation: "The current operational plan is ready for analysis.",
          trigger:
            sharedDescription ??
            "No operational disruption is currently applied.",
          what_went_wrong:
            sharedDescription ??
            "No operational disruption is currently applied.",
          unavailable_resources: disruptionResources(shared.disruption),
          question:
            "Which validated recovery best protects deadlines while limiting customer appointment changes?",
          what_to_watch: [
            "Affected visits and dependent battery work",
            "No-action impact versus validated recovery options",
            "Customer appointments that must move",
          ],
          success_criterion:
            "Protect commitments without violating inventory, skills, crew limits, appointments, or locks.",
          truth_label:
            "Synthetic installation portfolio; operational impacts and costs are modeled.",
        }
      : undefined);
  const backHref = shared ? primaryHref(shared) : location.pathname;
  return (
    <main>
      <nav className="advanced-nav" aria-label="Analysis navigation">
        <span>
          <strong>Advanced Analysis</strong>
          <small>Scrollable workspace</small>
        </span>
        <a href={backHref} data-testid="live-canvas-link">
          ← Back to main planner
        </a>
      </nav>
      <Header
        scenario={scenario.data}
        scenarios={scenarios.data ?? []}
        onScenario={reset}
        onReset={() => reset()}
        theme={theme}
        onTheme={toggleTheme}
      />
      <ScenarioBriefing
        key={scenarioId}
        report={briefingNarrative}
        primaryActive={primaryActive}
        disabled={!!busy || mockMode}
        hasDisruption={!!preset?.primary_disruption.length}
        activeCopy={sharedBannerCopy}
        onApply={() => {
          if (preset) {
            replaceEdits(preset.primary_disruption);
            setBaselineAnalysis(revision + 1);
          }
        }}
      />
      {shared && (
        <aside className="panel padded" data-testid="shared-recovery-context">
          <strong>Continuing the primary-page analysis</strong>
          <p>{sharedDescription}</p>
          {shared.protectedHomes.length > 0 && (
            <p>
              Protected homes: {shared.protectedHomes.join(", ")}. Their current
              appointments remain locked in this analysis.
            </p>
          )}
          <small>
            Advanced Analysis uses the same scenario and operational changes as
            the main planner.
          </small>
        </aside>
      )}
      {preset && mockMode && (
        <p role="status" className="panel padded">
          Use live API mode to run the synthetic scenario suite.
        </p>
      )}
      {scenarioId === "value_sensitive" && (
        <PolicyComparison
          key={`${scenarioId}/${revision}`}
          scenarioId={scenarioId}
          revision={revision}
          edits={edits}
        />
      )}
      {disruption ? (
        <RecoveryCanvas
          key={`${scenarioId}:${session}:${preset ? revision : 0}`}
          scenario={scenario.data}
          disruption={disruption}
          narrative={narrative}
          currentPlan={sharedCurrentPlan}
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
          <strong>Baseline plan</strong>
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
