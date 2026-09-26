import { useEffect, useState } from "react";
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
import { downloadPlan } from "../lib/export";
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
  const [theme, setTheme] = useState("light");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
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
        plan={result}
        scenarios={scenarios.data ?? []}
        onScenario={reset}
        theme={theme}
        onTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
      />
      <EditControls
        key={scenarioId}
        scenario={scenario.data}
        edits={edits}
        onEdit={edit}
        onReset={() => reset()}
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
