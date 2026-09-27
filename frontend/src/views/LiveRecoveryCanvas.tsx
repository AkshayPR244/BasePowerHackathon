import "../design/live-canvas.css";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, mockMode, unwrap } from "../api/client";
import type { Schema } from "../api/types";
import { dateLabel } from "../lib/format";
import { statusLabel, validationLabel } from "../lib/recovery";
import { OptionFrontier } from "../components/OptionFrontier";
import { PlanFigure, type CanvasTool } from "../components/PlanFigure";
import { SelectedRecovery } from "../components/SelectedRecovery";
import { TriggerRail } from "../components/TriggerRail";
import { useTheme } from "./useTheme";

type Disruption = Schema["RecoveryOptionsRequest"]["disruption"][number];
type Intervention = Schema["EvaluateRequest"]["interventions"][number];
type PlannedInstall = Schema["PlannedInstall"];
type Assignment = Schema["Assignment"];
type RecoveryOption = Schema["RecoveryOption"];

interface PreviousPlan {
  revision: number;
  manualLabel: string;
  movementBaseline: RecoveryOption | null;
  option: RecoveryOption;
  options: RecoveryOption[];
  disruption: Disruption[];
}

interface Sandbox {
  revision: number;
  disruption: Disruption[];
  protectedHomes: string[];
  headline: string;
}

const initialSandbox: Sandbox = {
  revision: 0,
  disruption: [],
  protectedHomes: [],
  headline: "The current plan is ready to change.",
};

function isValid(option: Schema["RecoveryOption"]) {
  return (
    (option.status === "feasible" || option.status === "optimal") &&
    option.result.objective !== null &&
    option.result.validation.checked &&
    option.result.validation.valid
  );
}

function currentPlanForProtection(
  rows: PlannedInstall[],
  protectedHomes: string[],
) {
  const protectedIds = new Set(protectedHomes);
  return rows.map((row) => ({
    ...row,
    locked: row.locked || protectedIds.has(row.site_id),
  }));
}

export function LiveRecoveryCanvas() {
  const [sandbox, setSandbox] = useState(initialSandbox);
  const [tool, setTool] = useState<CanvasTool>("knockout");
  const [traceHomeId, setTraceHomeId] = useState<string | null>(null);
  const [selectedVisit, setSelectedVisit] = useState<string | null>(null);
  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [evaluatedOption, setEvaluatedOption] = useState<
    Schema["RecoveryOption"] | null
  >(null);
  const [evaluationPending, setEvaluationPending] = useState(false);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  const [manualLabel, setManualLabel] = useState("");
  const [transitionMessage, setTransitionMessage] = useState("");
  const [previousPlan, setPreviousPlan] = useState<PreviousPlan | null>(null);
  const [movementBaseline, setMovementBaseline] =
    useState<RecoveryOption | null>(null);
  const [notice, setNotice] = useState("");
  const [approval, setApproval] = useState<Schema["ApproveResult"] | null>(
    null,
  );
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const latestRevision = useRef(sandbox.revision);
  // Any change to the option in view invalidates a pending approval.
  const approvalToken = useRef(0);
  const { theme, toggleTheme } = useTheme();

  const scenario = useQuery({
    queryKey: ["recovery-scenario", "standard"],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/scenarios/{scenario_id}", {
          params: { path: { scenario_id: "standard" } },
        }),
      ),
  });

  const currentPlan = scenario.data
    ? currentPlanForProtection(
        scenario.data.current_plan,
        sandbox.protectedHomes,
      )
    : undefined;
  const recovery = useQuery({
    queryKey: [
      "live-recovery-options",
      "standard",
      sandbox.revision,
      sandbox.disruption,
      sandbox.protectedHomes,
    ],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/recovery/options", {
          body: {
            scenario_id: "standard",
            revision: sandbox.revision,
            current_plan: currentPlan,
            disruption: sandbox.disruption,
            interactive: true,
          },
        }),
      ),
    enabled: !!scenario.data,
    staleTime: 0,
    retry: false,
  });

  const allOptions = recovery.data
    ? [
        recovery.data.no_action,
        ...recovery.data.options,
        ...(evaluatedOption?.result.revision === sandbox.revision
          ? [evaluatedOption]
          : []),
      ]
    : [];
  const validOptions = allOptions.filter(isValid);
  const noAction = validOptions.find((option) => option.kind === "no_action");
  const selectedOption =
    validOptions.find((option) => option.option_id === selectedOptionId) ??
    (sandbox.disruption.length === 0 && sandbox.protectedHomes.length === 0
      ? noAction
      : undefined) ??
    validOptions.find((option) => option.lowest_modeled_cost) ??
    noAction ??
    validOptions[0];
  const working =
    scenario.isPending ||
    recovery.isPending ||
    recovery.isFetching ||
    evaluationPending;
  const hasFreshRecovery = recovery.data?.revision === sandbox.revision;
  const showPrevious = previousPlan !== null && (!hasFreshRecovery || working);
  const figureOption = showPrevious ? previousPlan.option : selectedOption;
  const figureOptions = showPrevious ? previousPlan.options : validOptions;
  const figureDisruption = showPrevious
    ? previousPlan.disruption
    : sandbox.disruption;
  const figureComparisonOption = showPrevious
    ? previousPlan.movementBaseline
    : hasFreshRecovery && !working && previousPlan
      ? previousPlan.option
      : movementBaseline;

  useEffect(() => {
    if (!working && hasFreshRecovery && previousPlan) {
      setMovementBaseline(previousPlan.option);
      setPreviousPlan(null);
      setTransitionMessage("");
    }
  }, [hasFreshRecovery, previousPlan, working]);

  const approvalKey = `${sandbox.revision}|${selectedOption?.option_id}`;
  useEffect(() => {
    approvalToken.current++;
    setApproval(null);
    setApprovalError(null);
    setApproving(false);
  }, [approvalKey]);

  const preservePreviousPlan = () => {
    if (!selectedOption) return;
    setPreviousPlan({
      revision: sandbox.revision,
      manualLabel,
      movementBaseline,
      option: selectedOption,
      options: validOptions,
      disruption: sandbox.disruption,
    });
  };

  const requestEvaluation = async (
    revision: number,
    disruption: Disruption[],
    interventions: Intervention[],
    plan: PlannedInstall[] | undefined,
  ) => {
    if (!plan) return;
    setEvaluationPending(true);
    setEvaluationError(null);
    try {
      const result = unwrap(
        await api.POST("/api/recovery/evaluate", {
          body: {
            scenario_id: "standard",
            revision,
            current_plan: plan,
            disruption,
            interventions,
            interactive: true,
          },
        }),
      );
      if (revision === latestRevision.current) setEvaluatedOption(result);
    } catch (error) {
      if (revision === latestRevision.current) {
        setEvaluationError(
          error instanceof Error ? error.message : "Manual evaluation failed.",
        );
      }
    } finally {
      if (revision === latestRevision.current) setEvaluationPending(false);
    }
  };

  const applyChange = (
    headline: string,
    edits: Disruption[],
    progress: string,
  ) => {
    preservePreviousPlan();
    setTransitionMessage(progress);
    const revision = sandbox.revision + 1;
    const disruption = [...sandbox.disruption, ...edits];
    latestRevision.current = revision;
    setApproval(null);
    setApprovalError(null);
    setEvaluatedOption(null);
    setEvaluationError(null);
    setSelectedOptionId(null);
    setSelectedVisit(null);
    setTraceHomeId(null);
    setNotice("");
    setManualLabel(headline);
    setSandbox((current) => ({
      ...current,
      revision,
      disruption,
      headline,
    }));
    void requestEvaluation(revision, disruption, [], currentPlan);
  };

  const changeProtection = (siteId: string) => {
    preservePreviousPlan();
    const protectedNow = sandbox.protectedHomes.includes(siteId);
    const protectedHomes = protectedNow
      ? sandbox.protectedHomes.filter((id) => id !== siteId)
      : [...sandbox.protectedHomes, siteId];
    const revision = sandbox.revision + 1;
    latestRevision.current = revision;
    const headline = protectedNow
      ? `Home ${siteId} is no longer protected.`
      : `Home ${siteId} is protected from movement.`;
    setTransitionMessage(
      protectedNow
        ? `Removing the pins from Home ${siteId}. Checking whether its visits can move.`
        : `Pinning Home ${siteId}'s visits to their current crews and days. Checking whether the other visits still fit.`,
    );
    setApproval(null);
    setEvaluatedOption(null);
    setSelectedOptionId(null);
    setTraceHomeId(null);
    setManualLabel(headline);
    setSandbox((current) => ({
      ...current,
      revision,
      protectedHomes,
      headline,
    }));
    const interventions: Intervention[] = protectedNow
      ? []
      : (scenario.data?.current_plan ?? [])
          .filter((row) => row.site_id === siteId)
          .map((row) => ({
            kind: "pin_visit",
            job_id: row.job_id ?? siteId,
          }));
    void requestEvaluation(
      revision,
      sandbox.disruption,
      interventions,
      scenario.data
        ? currentPlanForProtection(scenario.data.current_plan, protectedHomes)
        : undefined,
    );
  };

  const effectiveCapacity = (crewId: string, day: string) => {
    const base =
      scenario.data?.crew_days.find(
        (crewDay) => crewDay.crew_id === crewId && crewDay.date === day,
      )?.available_min ?? 0;
    return sandbox.disruption.reduce((capacity, edit) => {
      if (
        edit.kind === "remove_crew_day" &&
        edit.crew_id === crewId &&
        edit.date === day
      )
        return 0;
      if (
        edit.kind === "reduce_crew_day" &&
        edit.crew_id === crewId &&
        edit.date === day
      )
        return edit.available_min;
      return capacity;
    }, base);
  };

  const applyCrewTool = (
    crewId: string,
    day: string,
    _availableMin: number,
  ) => {
    const currentCapacity = effectiveCapacity(crewId, day);
    if (currentCapacity <= 0) {
      setNotice(
        `Crew ${crewId} has no remaining capacity on ${dateLabel(day)}.`,
      );
      return;
    }
    if (tool === "knockout") {
      applyChange(
        `Crew ${crewId} loses ${dateLabel(day)}.`,
        [{ kind: "remove_crew_day", crew_id: crewId, date: day }],
        `Crew ${crewId} has no capacity on ${dateLabel(day)}. Reassigning its visits and checking deadlines.`,
      );
    } else if (tool === "halfday") {
      const half = Math.floor(currentCapacity / 2);
      if (half >= currentCapacity) return;
      applyChange(
        `Crew ${crewId} has a half day on ${dateLabel(day)}.`,
        [
          {
            kind: "reduce_crew_day",
            crew_id: crewId,
            date: day,
            available_min: half,
          },
        ],
        `Crew ${crewId} keeps ${half} of ${currentCapacity} min on ${dateLabel(day)}. Checking which visits move or miss their deadline.`,
      );
    } else {
      setNotice("Choose a crew-day tool, or click a visit.");
    }
  };

  const applyVisitTool = (assignment: Assignment) => {
    const currentScenario = scenario.data;
    if (!currentScenario) return;
    const site = currentScenario.sites.find(
      (entry) => entry.site_id === assignment.site_id,
    );
    if (!site) return;
    const jobId = assignment.job_id ?? site.visits[0]?.job_id ?? site.site_id;
    if (tool === "knockout" || tool === "halfday") {
      if (!assignment.crew_id || !assignment.date) {
        setNotice("Click a crew-day to change its capacity.");
        return;
      }
      applyCrewTool(
        assignment.crew_id,
        assignment.date,
        effectiveCapacity(assignment.crew_id, assignment.date),
      );
      return;
    }
    if (tool === "trace") {
      setTraceHomeId(site.site_id);
      setSelectedVisit(jobId);
      setNotice(
        `Tracing home ${site.site_id}. Hover a moved visit to reveal its former slot.`,
      );
      return;
    }
    if (tool === "protect") {
      changeProtection(site.site_id);
      return;
    }
    if (tool === "long") {
      const displayedCrewDay = currentScenario.crew_days.find(
        (day) =>
          day.crew_id === assignment.crew_id && day.date === assignment.date,
      );
      if (!displayedCrewDay && assignment.crew_id.startsWith("TEMP")) {
        setNotice(
          "This visit uses temporary capacity. Choose a base-crew visit to mark it running long.",
        );
        return;
      }
      const original = displayedCrewDay
        ? { crew_id: assignment.crew_id, date: assignment.date }
        : currentScenario.current_plan.find(
            (row) =>
              row.job_id === jobId ||
              (!row.job_id && row.site_id === site.site_id),
          );
      if (!original) {
        setNotice(`No current visit for ${site.site_id} can be extended.`);
        return;
      }
      const available = effectiveCapacity(original.crew_id, original.date);
      const duration =
        site.visits.find((visit) => visit.job_id === jobId)?.duration_min ??
        site.duration_min;
      const reduced = Math.max(0, available - duration);
      if (reduced >= available) return;
      applyChange(
        `${site.site_id} runs long. Crew ${original.crew_id} loses ${duration} min on ${dateLabel(original.date)}.`,
        [
          {
            kind: "reduce_crew_day",
            crew_id: original.crew_id,
            date: original.date,
            available_min: reduced,
          },
        ],
        `Crew ${original.crew_id} loses ${duration} min on ${dateLabel(original.date)} because ${site.site_id}'s visit runs long. Checking which other visits move.`,
      );
      return;
    }
    if (tool === "reschedule") {
      const rows = currentScenario.current_plan.filter(
        (row) => row.site_id === site.site_id,
      );
      const edits: Disruption[] = rows.map((row) => {
        const visitId =
          row.job_id ??
          site.visits.find((visit) => visit.visit_type === "battery_day")
            ?.job_id ??
          site.site_id;
        return {
          kind: "change_appointment",
          job_id: visitId,
          available_from: nextBusinessDay(row.date),
        };
      });
      if (edits.length === 0) {
        setNotice(`No current visit for ${site.site_id} can be rescheduled.`);
        return;
      }
      applyChange(
        `Home ${site.site_id} needs a new date.`,
        edits,
        `Setting Home ${site.site_id}'s current visits to start no earlier than the next business day. Checking crew capacity and deadlines.`,
      );
      return;
    }
    setSelectedVisit(jobId);
    setNotice("Choose a visit-level tool or a crew-day.");
  };

  const applyRandom = () => {
    const currentScenario = scenario.data;
    if (!currentScenario) return;
    const bookedSlots = new Set(
      currentScenario.current_plan.map((row) => `${row.crew_id}|${row.date}`),
    );
    const days = currentScenario.crew_days.filter(
      (day) =>
        bookedSlots.has(`${day.crew_id}|${day.date}`) &&
        effectiveCapacity(day.crew_id, day.date) > 0,
    );
    if (days.length === 0) {
      setNotice("No crew-day can take another trigger.");
      return;
    }
    if (mockMode) {
      const recorded = days.find(
        (day) => day.crew_id === "BA" && day.date === "2018-06-14",
      );
      if (!recorded) {
        setNotice(
          "The recorded demo trigger is unavailable. Reset the demo or use the live API.",
        );
        return;
      }
      setTool("knockout");
      applyChange(
        `Crew ${recorded.crew_id} loses ${dateLabel(recorded.date)}.`,
        [
          {
            kind: "remove_crew_day",
            crew_id: recorded.crew_id,
            date: recorded.date,
          },
        ],
        `Crew ${recorded.crew_id} has no capacity on ${dateLabel(recorded.date)}. Reassigning its visits and checking deadlines.`,
      );
      return;
    }
    const choice = days[Math.floor(Math.random() * days.length)];
    if (Math.random() < 0.5) {
      setTool("knockout");
      applyChange(
        `Crew ${choice.crew_id} loses ${dateLabel(choice.date)}.`,
        [
          {
            kind: "remove_crew_day",
            crew_id: choice.crew_id,
            date: choice.date,
          },
        ],
        `Crew ${choice.crew_id} has no capacity on ${dateLabel(choice.date)}. Reassigning its visits and checking deadlines.`,
      );
    } else {
      const half = Math.floor(
        effectiveCapacity(choice.crew_id, choice.date) / 2,
      );
      setTool("halfday");
      applyChange(
        `Crew ${choice.crew_id} has a half day on ${dateLabel(choice.date)}.`,
        [
          {
            kind: "reduce_crew_day",
            crew_id: choice.crew_id,
            date: choice.date,
            available_min: half,
          },
        ],
        `Crew ${choice.crew_id} keeps ${half} min on ${dateLabel(choice.date)}. Checking which visits move or miss their deadline.`,
      );
    }
  };

  const reset = () => {
    preservePreviousPlan();
    const revision = sandbox.revision + 1;
    latestRevision.current = revision;
    setTransitionMessage(
      "Clearing disruptions and restoring the current plan.",
    );
    setTool("knockout");
    setSelectedOptionId(null);
    setSelectedVisit(null);
    setTraceHomeId(null);
    setApproval(null);
    setApprovalError(null);
    setEvaluatedOption(null);
    setEvaluationPending(false);
    setEvaluationError(null);
    setManualLabel("");
    setNotice("");
    setSandbox({
      revision,
      disruption: [],
      protectedHomes: [],
      headline: "The current plan is restored.",
    });
  };

  const approve = async (option: RecoveryOption) => {
    if (!recovery.data || !isValid(option)) return;
    const token = approvalToken.current;
    setApproving(true);
    setApprovalError(null);
    try {
      const result = unwrap(
        await api.POST("/api/recovery/approve", {
          body: {
            scenario_id: "standard",
            revision: recovery.data.revision,
            option,
          },
        }),
      );
      if (token === approvalToken.current) setApproval(result);
    } catch (error) {
      if (token === approvalToken.current)
        setApprovalError(
          error instanceof Error ? error.message : "Approval failed.",
        );
    } finally {
      if (token === approvalToken.current) setApproving(false);
    }
  };

  const totalPlans = allOptions.length;
  const checkedPlans = allOptions.filter(isValid).length;
  const withheldPlans = allOptions.filter((option) => !isValid(option));
  const consequence = recovery.data
    ? `${recovery.data.impact.affected_job_ids.length} visits displaced. With no action, ${recovery.data.no_action.counts.deadlines_missed} deadlines slip. Re-planned ${recovery.data.options.length} recovery options; ${checkedPlans} of ${totalPlans} plans passed validation.`
    : "A synthetic plan. Costs are modeled.";

  if (scenario.isError) {
    return (
      <main className="live-startup" role="alert">
        {scenario.error.message}
      </main>
    );
  }

  return (
    <main className="live-app" data-testid="live-recovery-canvas">
      <header className="live-header">
        <div className="headline-copy">
          <h1 data-testid="live-headline">{sandbox.headline}</h1>
          <p data-testid="live-subline">
            {working
              ? transitionMessage ||
                "The previous plan stays visible while recovery options are checked."
              : recovery.data
                ? consequence
                : "Loading the current plan…"}
          </p>
          {notice && (
            <p className="interaction-note" role="status">
              {notice}
            </p>
          )}
          {evaluationError && (
            <p className="request-error" role="alert">
              Manual evaluation failed: {evaluationError}
            </p>
          )}
        </div>
        <div className="source-labels">
          {scenario.data?.config.synthetic && <span>Synthetic plan</span>}
          <span>Costs are modeled</span>
          <button
            type="button"
            className="header-button"
            onClick={toggleTheme}
            aria-label={`Use ${theme === "dark" ? "light" : "dark"} theme`}
            data-testid="theme-toggle"
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
          <a
            className="header-button"
            href="?view=workspace"
            data-testid="workspace-link"
          >
            Advanced: scenario suite and baseline plan
          </a>
        </div>
      </header>

      <TriggerRail
        active={tool}
        disabled={!scenario.data || working}
        onSelect={(next) => {
          setTool(next);
          setTraceHomeId(null);
          setNotice("");
        }}
        onRandom={applyRandom}
        onReset={reset}
      />

      {recovery.error && (
        <p className="request-error" role="alert">
          {recovery.error instanceof Error
            ? recovery.error.message
            : "Recovery options failed."}
        </p>
      )}

      <div
        className={`live-figures ${working && !showPrevious ? "figures-loading" : ""} ${showPrevious ? "figures-stale" : ""}`}
        aria-busy={working}
        inert={showPrevious}
        data-testid={working ? "working-state" : "live-results"}
      >
        {showPrevious && (
          <div
            className="canvas-progress-band"
            role="status"
            data-testid="previous-result"
          >
            <strong>Previous result · approval paused</strong>
            <span>
              Showing revision {previousPlan.revision} while the planner checks
              the latest change.
            </span>
          </div>
        )}
        {working && !showPrevious ? (
          <div className="canvas-progress" role="status">
            Loading the synthetic current plan and checking its recovery
            options…
          </div>
        ) : (showPrevious || recovery.data) && scenario.data ? (
          <>
            <PlanFigure
              scenario={scenario.data}
              option={figureOption}
              comparisonOption={figureComparisonOption}
              disruption={figureDisruption}
              tool={tool}
              traceHomeId={traceHomeId}
              selectedVisit={selectedVisit}
              disabled={showPrevious || !figureOption}
              onCrewDay={applyCrewTool}
              onVisit={applyVisitTool}
              onTrace={(siteId) => {
                setTraceHomeId(siteId);
                setNotice(
                  `Tracing home ${siteId}. Hover a moved visit to reveal its former slot.`,
                );
              }}
            />
            <div className="options-column">
              <OptionFrontier
                options={figureOptions}
                selectedId={figureOption?.option_id ?? null}
                customLabel={
                  showPrevious ? previousPlan.manualLabel : manualLabel
                }
                onSelect={(id) => {
                  setSelectedOptionId(id);
                  setSelectedVisit(null);
                  setApproval(null);
                }}
              />
              {checkedPlans < totalPlans && (
                <div className="validation-warning" role="status">
                  {withheldPlans.map((option) => {
                    const report = option.result.validation;
                    const reason = !report.checked
                      ? "Independent validation did not run."
                      : report.issues.length
                        ? report.issues.map((issue) => issue.message).join("; ")
                        : option.result.message;
                    return (
                      <p key={option.option_id} data-testid="withheld-option">
                        {option.action_label} · {statusLabel(option)} ·{" "}
                        {validationLabel(option)}. {reason}
                      </p>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        ) : null}
      </div>

      {(!working || showPrevious) && (
        <SelectedRecovery
          option={figureOption}
          labelOverride={
            figureOption?.kind === "custom"
              ? showPrevious
                ? previousPlan.manualLabel
                : manualLabel
              : undefined
          }
          stale={showPrevious}
          busy={approving || working || showPrevious}
          approval={approval}
          error={approvalError}
          onApprove={(option) => void approve(option)}
        />
      )}
      {recovery.data?.stub && (
        <p className="response-note">
          Fixture response. The recovery service did not calculate these
          options.
        </p>
      )}
    </main>
  );
}

function nextBusinessDay(day: string) {
  const date = new Date(`${day}T12:00:00Z`);
  do date.setUTCDate(date.getUTCDate() + 1);
  while (date.getUTCDay() === 0 || date.getUTCDay() === 6);
  return date.toISOString().slice(0, 10);
}
