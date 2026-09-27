import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "../api/client";
import type { Scenario, Schema } from "../api/types";
import { DisruptionBar } from "../components/DisruptionBar";
import { CascadeStrip } from "../components/CascadeStrip";
import { OptionCard } from "../components/OptionCard";
import { OptionPanel } from "../components/OptionPanel";
import { EvaluationControls } from "../components/EvaluationControls";
import { AssumptionsPanel } from "../components/AssumptionsPanel";
import { CrewCalendar } from "../components/CrewCalendar";
import { SiteMap } from "../components/SiteMap";
import {
  describeDisruption,
  earliestDate,
  hasValidPlan,
  slotsOffPlan,
  statusLabel,
  validationLabel,
  type Disruption,
  type Intervention,
  type Option,
} from "../lib/recovery";

type Approval = { optionId: string; result: Schema["ApproveResult"] };
const errorText = (cause: unknown, fallback: string) =>
  cause instanceof Error ? cause.message : fallback;

// Mount with a key per scenario and demo session so every piece of state resets.
export function RecoveryCanvas({
  scenario,
  disruption,
  mockMode,
}: {
  scenario: Scenario;
  disruption: Disruption[];
  mockMode: boolean;
}) {
  const scenarioId = scenario.scenario_id;
  const [overrides, setOverrides] = useState<Record<string, number>>({});
  const [requestRevision, setRequestRevision] = useState(1);
  const recoveryOptions = useQuery({
    queryKey: ["recovery-options", scenarioId, disruption, overrides],
    queryFn: async () =>
      unwrap(
        await api.POST("/api/recovery/options", {
          body: {
            scenario_id: scenarioId,
            revision: requestRevision,
            disruption,
            economics_overrides: Object.keys(overrides).length
              ? overrides
              : undefined,
            interactive: false,
          },
        }),
      ),
    placeholderData: (previousData) => previousData,
  });
  const lastGood = useRef<Schema["RecoveryOptionsResult"] | undefined>(
    undefined,
  );
  if (recoveryOptions.data && !recoveryOptions.isError)
    lastGood.current = recoveryOptions.data;
  const data = recoveryOptions.data ?? lastGood.current;
  const optionsError = recoveryOptions.isError
    ? errorText(recoveryOptions.error, "The recovery options failed.")
    : null;
  const options: Option[] = data ? [data.no_action, ...data.options] : [];
  const optionIds = options.map((option) => option.option_id).join("|");

  const [selectedOptionId, setSelectedOptionId] = useState<string | null>(null);
  const [selectedSite, setSelectedSite] = useState<string | null>(null);
  const [cascadeStep, setCascadeStep] = useState<number | null>(null);
  const selectedOption =
    options.find((option) => option.option_id === selectedOptionId) ??
    options.find((option) => option.lowest_modeled_cost) ??
    options[0];

  // Any change to the option in view invalidates pending approve and evaluate responses.
  const viewToken = useRef(0);
  const viewKey = `${selectedOption?.option_id}|${data?.revision}|${JSON.stringify(overrides)}`;
  const [approval, setApproval] = useState<Approval | null>(null);
  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<Option | null>(null);
  const [evaluationPending, setEvaluationPending] = useState(false);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  useEffect(() => {
    viewToken.current++;
    setApproval(null);
    setApproving(false);
    setApproveError(null);
    setEvaluation(null);
    setEvaluationPending(false);
    setEvaluationError(null);
  }, [viewKey]);

  const approve = async (option: Option) => {
    if (!data) return;
    const token = viewToken.current;
    setApproving(true);
    setApproveError(null);
    try {
      const result = unwrap(
        await api.POST("/api/recovery/approve", {
          body: { scenario_id: scenarioId, revision: data.revision, option },
        }),
      );
      if (token === viewToken.current)
        setApproval({ optionId: option.option_id, result });
    } catch (cause) {
      if (token === viewToken.current)
        setApproveError(errorText(cause, "Approval failed."));
    } finally {
      if (token === viewToken.current) setApproving(false);
    }
  };
  const evaluate = async (
    changedDisruption: Disruption[],
    interventions: Intervention[],
  ) => {
    if (!data) return;
    const token = viewToken.current;
    setEvaluationPending(true);
    setEvaluationError(null);
    setEvaluation(null);
    try {
      const result = unwrap(
        await api.POST("/api/recovery/evaluate", {
          body: {
            scenario_id: scenarioId,
            revision: data.revision,
            disruption: changedDisruption,
            interventions,
            economics_overrides: Object.keys(overrides).length
              ? overrides
              : undefined,
            interactive: true,
          },
        }),
      );
      if (token === viewToken.current) setEvaluation(result);
    } catch (cause) {
      if (token === viewToken.current)
        setEvaluationError(errorText(cause, "The recovery change failed."));
    } finally {
      if (token === viewToken.current) setEvaluationPending(false);
    }
  };
  const applyOverrides = (values: Record<string, number>) => {
    setRequestRevision((revision) => revision + 1);
    setOverrides(values);
  };

  useEffect(() => {
    const ids = optionIds ? optionIds.split("|") : [];
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (document.querySelector("dialog[open]")) return;
      const target = event.target as HTMLElement;
      if (
        target.isContentEditable ||
        ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)
      )
        return;
      const optionNumber = Number(event.key);
      if (Number.isInteger(optionNumber) && optionNumber > 0) {
        const id = ids[optionNumber - 1];
        if (!id) return;
        setSelectedOptionId(id);
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
  }, [optionIds]);

  const description = describeDisruption(disruption, scenario);
  const validPlan = selectedOption && hasValidPlan(selectedOption);
  const ghosts =
    selectedOption && validPlan ? slotsOffPlan(selectedOption) : [];
  const changedJobIds = selectedOption
    ? selectedOption.diff_vs_original.changes.map(
        (change) => change.job_id ?? change.site_id,
      )
    : [];
  const highlighted =
    cascadeStep === null
      ? []
      : (data?.impact.cascade[cascadeStep]?.job_ids ?? []);
  const noLowest =
    options.length > 0 && !options.some((o) => o.lowest_modeled_cost);
  return (
    <div className="canvas" data-testid="recovery-canvas">
      <DisruptionBar
        description={description}
        result={data}
        loading={recoveryOptions.isPending}
        error={optionsError}
      />
      {data && (
        <>
          <CascadeStrip
            cascade={data.impact.cascade}
            selected={cascadeStep}
            onSelect={setCascadeStep}
          />
          <section
            className="option-list"
            aria-label="Recovery options"
            data-testid="option-list"
          >
            <div className="panel-heading">
              <h2>Recovery options</h2>
              <span>
                {recoveryOptions.isFetching && !recoveryOptions.isPending
                  ? "Recalculating…"
                  : "Compared with no action"}
              </span>
            </div>
            {noLowest && (
              <p className="option-note" data-testid="no-lowest-note">
                No option has a lower modeled cost than the others. Compare
                deadlines missed and customers to reschedule.
              </p>
            )}
            {optionsError && (
              <p className="option-note error" role="alert">
                These options use the last assumptions that worked.
              </p>
            )}
            <div className="option-grid">
              {options.map((option, index) => (
                <OptionCard
                  key={option.option_id}
                  option={option}
                  shortcut={String(index + 1)}
                  selected={selectedOption?.option_id === option.option_id}
                  onSelect={setSelectedOptionId}
                />
              ))}
            </div>
          </section>
          <div className="canvas-grid">
            <CrewCalendar
              scenario={scenario}
              title={
                selectedOption
                  ? `Plan lanes · ${selectedOption.action_label}`
                  : "Plan lanes"
              }
              notice={
                selectedOption && !validPlan
                  ? `“${selectedOption.action_label}” has no validated plan to draw. ${statusLabel(selectedOption)} · ${validationLabel(selectedOption)}.`
                  : undefined
              }
              plan={validPlan ? selectedOption.result : null}
              selected={selectedSite}
              highlightedJobIds={highlighted}
              lostCrewDays={disruption.flatMap((edit) =>
                edit.kind === "remove_crew_day" ? [edit] : [],
              )}
              ghosts={ghosts}
              changedJobIds={validPlan ? changedJobIds : []}
              arcJobIds={[
                ...changedJobIds,
                ...data.impact.affected_job_ids,
                ...highlighted,
              ]}
              focusDate={earliestDate(disruption)}
              onSelect={setSelectedSite}
            />
            <aside className="canvas-side">
              <OptionPanel
                option={selectedOption}
                mockLimited={mockMode && selectedOption?.kind !== "rebalance"}
                approving={approving}
                approval={
                  approval && approval.optionId === selectedOption?.option_id
                    ? approval.result
                    : null
                }
                error={approveError}
                onApprove={(option) => void approve(option)}
              />
            </aside>
          </div>
          <div className="canvas-lower">
            <div className="canvas-lower-main">
              <EvaluationControls
                scenario={scenario}
                disruption={disruption}
                option={validPlan ? selectedOption : undefined}
                onEvaluate={(next, interventions) =>
                  void evaluate(next, interventions)
                }
                pending={evaluationPending}
                result={evaluation}
                error={evaluationError}
              />
              <AssumptionsPanel
                assumptions={data.economic_assumptions}
                overrides={overrides}
                stub={data.stub}
                recalculating={
                  recoveryOptions.isFetching && !recoveryOptions.isPending
                }
                error={optionsError}
                onApply={applyOverrides}
                onReset={() => applyOverrides({})}
              />
            </div>
            <SiteMap
              scenario={scenario}
              plan={validPlan ? selectedOption.result : null}
              selected={selectedSite}
              affectedJobIds={data.impact.affected_job_ids}
              compact
              onSelect={setSelectedSite}
            />
          </div>
        </>
      )}
    </div>
  );
}
