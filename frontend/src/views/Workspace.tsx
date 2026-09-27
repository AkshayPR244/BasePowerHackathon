import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../api/client";
import type { Schema } from "../api/types";
import { mockMode } from "../api/client";
import { usePlanner } from "../state/usePlanner";
import { Header } from "../components/Header";
import { MetricsStrip } from "../components/MetricsStrip";
import { CrewCalendar } from "../components/CrewCalendar";
import { DeferredList } from "../components/DeferredList";
import { SiteMap } from "../components/SiteMap";
import { Inspector } from "../components/Inspector";
import { EditControls } from "../components/EditControls";
import { ComparePanel } from "../components/ComparePanel";
import { DisruptionBar } from "../components/DisruptionBar";
import { CascadeStrip } from "../components/CascadeStrip";
import { OptionCard } from "../components/OptionCard";
import { OptionPanel } from "../components/OptionPanel";
import { EvaluationControls } from "../components/EvaluationControls";
import { AssumptionsPanel } from "../components/AssumptionsPanel";
import { PolicyComparison } from "../components/PolicyComparison";
import { ScenarioBriefing } from "../components/ScenarioBriefing";
import { narrativeFor } from "../narratives";
import { presetFor } from "../scenario-presets";
import { downloadPlan } from "../lib/export";

const standardStormDisruption: Schema["RecoveryOptionsRequest"]["disruption"] =
  [
    { kind: "remove_crew_day", crew_id: "IA", date: "2018-06-14" },
    { kind: "remove_crew_day", crew_id: "IB", date: "2018-06-14" },
    { kind: "remove_crew_day", crew_id: "BA", date: "2018-06-14" },
  ];

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
  const [theme, setTheme] = useState("light");
  const [selectedCascadeStep, setSelectedCascadeStep] = useState<number | null>(
    null,
  );
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [approval, setApproval] = useState<Schema["ApproveResult"] | null>(
    null,
  );
  const [approveError, setApproveError] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<Schema["RecoveryOption"] | null>(
    null,
  );
  const [evaluationPending, setEvaluationPending] = useState(false);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  const [economicsOverrides, setEconomicsOverrides] = useState<
    Record<string, number>
  >({});
  const requestScope = useRef("");
  const approvalToken = useRef(0);
  const evaluationToken = useRef(0);
  requestScope.current = `${scenarioId}/${revision}/${JSON.stringify(economicsOverrides)}`;
  const narrative = narrativeFor(scenarioId);
  const preset = presetFor(scenarioId);
  const isSuite = !!preset;
  const [baselineAnalysis, setBaselineAnalysis] = useState<number | null>(null);
  const primaryActive =
    !!preset &&
    (preset.primary_disruption.length === 0
      ? baselineAnalysis === revision
      : JSON.stringify(edits) === JSON.stringify(preset.primary_disruption));
  const recoveryEnabled = isSuite
    ? edits.length > 0 || baselineAnalysis === revision
    : scenarioId === "standard";
  const activeDisruption = isSuite ? edits : standardStormDisruption;
  useEffect(() => {
    setBaselineAnalysis(null);
    setEconomicsOverrides({});
  }, [scenarioId]);
  useEffect(() => {
    approvalToken.current++;
    evaluationToken.current++;
    setApproving(false);
    setEvaluationPending(false);
    setApproval(null);
    setApproveError(null);
    setSelectedOptionId(null);
    setSelectedCascadeStep(null);
    setEvaluation(null);
  }, [scenarioId, revision, economicsOverrides]);
  const recoveryOptions = useQuery({
    queryKey: [
      "recovery-options",
      scenarioId,
      revision,
      activeDisruption,
      economicsOverrides,
    ],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/recovery/options", {
          body: {
            scenario_id: scenarioId,
            revision,
            disruption: activeDisruption,
            economics_overrides:
              Object.keys(economicsOverrides).length > 0
                ? economicsOverrides
                : undefined,
            interactive: false,
          },
        }),
      ),
    enabled: recoveryEnabled,
  });
  const options =
    recoveryEnabled && recoveryOptions.data
      ? [recoveryOptions.data.no_action, ...recoveryOptions.data.options]
      : [];
  const selectedOption =
    options.find((option) => option.option_id === selectedOptionId) ??
    options.find((option) => option.lowest_modeled_cost) ??
    options[0];
  const displayPlan = isSuite ? (selectedOption?.result ?? result) : result;
  const displayValid = !!displayPlan?.objective && displayPlan.validation.valid;
  const approveSelectedOption = async () => {
    if (!selectedOption) return;
    const scope = requestScope.current,
      token = ++approvalToken.current;
    const isCurrent = () =>
      scope === requestScope.current && token === approvalToken.current;
    setApproving(true);
    setApproveError(null);
    try {
      const response = unwrap(
        await api.POST("/api/recovery/approve", {
          body: {
            scenario_id: scenarioId,
            revision: recoveryOptions.data?.revision ?? 1,
            option: selectedOption,
          },
        }),
      );
      if (isCurrent()) setApproval(response);
    } catch (cause) {
      if (isCurrent())
        setApproveError(
          cause instanceof Error ? cause.message : "Approval failed.",
        );
    } finally {
      if (isCurrent()) setApproving(false);
    }
  };
  const evaluateChange = async (
    disruption: Schema["EvaluateRequest"]["disruption"],
    interventions: Schema["EvaluateRequest"]["interventions"],
  ) => {
    const scope = requestScope.current,
      token = ++evaluationToken.current;
    const isCurrent = () =>
      scope === requestScope.current && token === evaluationToken.current;
    setEvaluationPending(true);
    setEvaluationError(null);
    setEvaluation(null);
    try {
      const response = unwrap(
        await api.POST("/api/recovery/evaluate", {
          body: {
            scenario_id: scenarioId,
            revision: (recoveryOptions.data?.revision ?? 1) + 1,
            disruption,
            interventions,
            interactive: true,
          },
        }),
      );
      if (isCurrent()) setEvaluation(response);
    } catch (cause) {
      if (isCurrent())
        setEvaluationError(
          cause instanceof Error
            ? cause.message
            : "The recovery change failed.",
        );
    } finally {
      if (isCurrent()) setEvaluationPending(false);
    }
  };
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const target = event.target as HTMLElement;
      if (
        target.isContentEditable ||
        ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)
      )
        return;
      const optionNumber = Number(event.key);
      if (optionNumber > 0 && optionNumber <= options.length) {
        setSelectedOptionId(options[optionNumber - 1].option_id);
        event.preventDefault();
      } else if (event.key.toLowerCase() === "a") {
        document
          .querySelector<HTMLButtonElement>("[data-testid='approve-option']")
          ?.click();
      } else if (event.key.toLowerCase() === "k") {
        document
          .querySelector<HTMLButtonElement>("[data-testid='knockout-crew-day']")
          ?.click();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [options.length]);
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
  if (!scenario.data)
    return (
      <main className="startup">Loading scenario and crew availability…</main>
    );
  return (
    <main>
      <Header
        scenario={scenario.data}
        plan={displayPlan}
        scenarios={scenarios.data ?? []}
        onScenario={reset}
        theme={theme}
        onTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
      />
      <ScenarioBriefing
        key={scenarioId}
        report={narrative}
        primaryActive={primaryActive}
        disabled={!!busy || mockMode}
        hasDisruption={!!preset?.primary_disruption.length}
        onApply={() => {
          if (preset) {
            replaceEdits(preset.primary_disruption);
            setBaselineAnalysis(revision + 1);
          }
        }}
      />
      {isSuite && mockMode && (
        <p role="status">
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
      <EditControls
        key={scenarioId}
        scenario={scenario.data}
        edits={edits}
        onEdit={edit}
        onReset={() => reset()}
      />
      {recoveryEnabled && (
        <>
          <DisruptionBar
            truthLabel={
              isSuite
                ? (narrative?.truth_label ??
                  "Synthetic installation portfolio; modeled operational disruption and costs.")
                : undefined
            }
            result={recoveryOptions.data}
            loading={recoveryOptions.isPending}
            error={
              recoveryOptions.error instanceof Error
                ? recoveryOptions.error.message
                : null
            }
          />
          {recoveryOptions.data && (
            <>
              <CascadeStrip
                cascade={recoveryOptions.data.impact.cascade}
                selected={selectedCascadeStep}
                onSelect={setSelectedCascadeStep}
              />
              <section
                className="option-list"
                aria-label="Recovery options"
                data-testid="option-list"
              >
                <div className="panel-heading">
                  <h2>Recovery options</h2>
                  <span>Compared with no action</span>
                </div>
                {narrative && (
                  <aside className="scenario-watch" aria-label="What to watch">
                    <strong>What to watch</strong>
                    <ul>
                      {narrative.what_to_watch.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </aside>
                )}
                <div className="option-grid">
                  {options.map((option) => (
                    <OptionCard
                      key={option.option_id}
                      option={option}
                      shortcut={String(options.indexOf(option) + 1)}
                      selected={selectedOption?.option_id === option.option_id}
                      onSelect={setSelectedOptionId}
                    />
                  ))}
                </div>
                {narrative && (
                  <p className="scenario-success">
                    Success criterion: {narrative.success_criterion}
                  </p>
                )}
                <OptionPanel
                  key={selectedOption?.option_id}
                  option={selectedOption}
                  canApprove={
                    !!selectedOption &&
                    selectedOption.result.validation.valid &&
                    ["optimal", "feasible"].includes(selectedOption.status) &&
                    (!mockMode || selectedOption.kind === "rebalance")
                  }
                  approving={approving}
                  approval={approval}
                  error={approveError}
                  onApprove={() => void approveSelectedOption()}
                />
                {!isSuite && (
                  <EvaluationControls
                    onEvaluate={(disruption, interventions) =>
                      void evaluateChange(disruption, interventions)
                    }
                    pending={evaluationPending}
                    result={evaluation}
                    error={evaluationError}
                  />
                )}
                <AssumptionsPanel
                  assumptions={recoveryOptions.data.economic_assumptions}
                  overrides={economicsOverrides}
                  stub={recoveryOptions.data.stub}
                  onApply={setEconomicsOverrides}
                />
              </section>
            </>
          )}
        </>
      )}
      <div className="workspace-toolbar">
        <div>
          <span className="eyebrow">PLAN / REVISION {revision}</span>
          <strong>
            {stale && !(isSuite && selectedOption)
              ? "Previous result · changes not solved"
              : displayPlan?.mode === "recovery"
                ? "Recovery plan"
                : "Strict plan"}
          </strong>
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
            disabled={
              !!busy ||
              (isSuite
                ? recoveryOptions.isFetching || !displayValid
                : stale || !validShape)
            }
            onClick={() => displayPlan && downloadPlan(displayPlan, "json")}
          >
            Export JSON
          </button>
          <button
            disabled={
              !!busy ||
              (isSuite
                ? recoveryOptions.isFetching || !displayValid
                : stale || !validShape)
            }
            onClick={() => displayPlan && downloadPlan(displayPlan, "csv")}
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
        {displayPlan && (
          <p className={displayPlan.status === "infeasible" ? "warning" : ""}>
            {displayPlan.message}
          </p>
        )}
        {result?.status === "infeasible" && !stale && (
          <p>
            No plan meets all commitments. Choose “Find recovery” to allow late
            installs and inspect the trade-offs.
          </p>
        )}
        {result?.validation.checked && !result.validation.valid && (
          <p role="alert" className="error">
            This result failed validation. Assignments are hidden and export is
            disabled.
          </p>
        )}
        {result?.input_issues.map((i, n) => (
          <p key={n} className="error">
            {JSON.stringify(i)}
          </p>
        ))}
      </div>
      <div
        className={
          stale && !(isSuite && selectedOption)
            ? "result-area stale"
            : "result-area"
        }
        aria-busy={!!busy}
      >
        <MetricsStrip
          plan={
            isSuite
              ? displayValid
                ? displayPlan
                : null
              : validShape
                ? result
                : null
          }
        />
        <div className="workspace-grid">
          <div className="main-column">
            <CrewCalendar
              scenario={scenario.data}
              plan={selectedOption?.result ?? (validShape ? result : null)}
              selected={selected}
              highlightedJobIds={
                selectedCascadeStep === null
                  ? []
                  : (recoveryOptions.data?.impact.cascade[selectedCascadeStep]
                      ?.job_ids ?? [])
              }
              lostCrewDays={(recoveryEnabled ? activeDisruption : []).filter(
                (edit) => edit.kind === "remove_crew_day",
              )}
              beforeAssignments={
                baseline?.assignments ??
                recoveryOptions.data?.no_action.result.assignments ??
                []
              }
              changedJobIds={
                selectedOption?.diff_vs_original.changes.map(
                  (change) => change.job_id ?? change.site_id,
                ) ?? []
              }
              onSelect={state.select}
            />
            <div className="lower-grid">
              <SiteMap
                scenario={scenario.data}
                plan={
                  isSuite
                    ? displayValid
                      ? displayPlan
                      : null
                    : validShape
                      ? result
                      : null
                }
                selected={selected}
                affectedJobIds={recoveryOptions.data?.impact.affected_job_ids}
                onSelect={state.select}
              />
              <DeferredList plan={displayPlan} onSelect={state.select} />
            </div>
            {diff && <ComparePanel diff={diff} />}
          </div>
          <Inspector
            scenario={scenario.data}
            plan={
              isSuite
                ? displayValid
                  ? displayPlan
                  : null
                : validShape
                  ? result
                  : null
            }
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
