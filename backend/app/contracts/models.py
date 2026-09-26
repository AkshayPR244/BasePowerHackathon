import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.enums import (
    Algorithm,
    CascadeKind,
    ChangeKind,
    DataKind,
    EconomicKind,
    InputIssueCode,
    JobState,
    Mode,
    ObjectivePolicy,
    OptionKind,
    PlanStatus,
    ReasonCode,
    StageStatus,
    ViolationCode,
    VisitType,
)
from app.contracts.units import KW, Days, Fraction, Id, KWh, Minutes, Usd

CONTRACT_VERSION = "1.0.0"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


# --- Inputs ---------------------------------------------------------------


class Visit(Contract):
    """One crew visit to a home. A two-visit home has an install, then a battery day."""

    job_id: Id
    visit_type: VisitType
    duration_min: Minutes
    required_skill: Id


class Site(Contract):
    site_id: Id
    cluster_id: Id
    program_id: Id
    ready_date: dt.date
    deadline: dt.date
    duration_min: Minutes
    required_skill: Id
    configuration_id: Id
    load_zone: Id
    profile_id: str | None = None
    lon: float
    lat: float
    visits: list[Visit] = Field(
        default=[],
        description="Empty: one visit described by duration_min and required_skill. "
        "Otherwise an install and a battery day; the deadline and energy value apply to "
        "the battery day, and duration_min / required_skill describe the battery day.",
    )


class Cluster(Contract):
    cluster_id: Id
    name: str
    travel_allowance_min: Minutes
    outline: list[tuple[float, float]] = Field(description="Closed ring of (lon, lat)")


class CrewDay(Contract):
    crew_id: Id
    date: dt.date
    available_min: Minutes
    skills: list[str]
    allowed_clusters: list[str]


class InventoryReceipt(Contract):
    configuration_id: Id
    available_date: dt.date
    quantity: int = Field(ge=0, description="Incoming units on this date, not a balance")


class PlannedInstall(Contract):
    """One row of the current installation plan that a disruption may force to change."""

    site_id: Id
    crew_id: Id
    date: dt.date
    locked: bool
    job_id: str | None = Field(default=None, description="Visit job; None for one-visit homes")


class BatteryConfig(Contract):
    configuration_id: Id
    capacity_kwh: KWh
    reserve_kwh: KWh
    charge_limit_kw: KW
    discharge_limit_kw: KW
    eta_charge: Fraction
    eta_discharge: Fraction


class ProvenanceNote(Contract):
    input: str = Field(description="File or field this note covers, e.g. sites.csv:deadline")
    kind: DataKind
    source: str
    manifest_id: str | None = None


class Parameter(Contract):
    """One operational number the model uses, with where it came from."""

    name: str
    value: float | str
    unit: str
    kind: DataKind
    derivation: str = Field(description="Rule, formula, or citation that produced the value")
    source: str | None = Field(default=None, description="URL or reference, when one exists")


class WeatherRule(Contract):
    """A crew-day is lost when any working hour meets either condition."""

    thunder: bool = Field(default=True, description="Lose the day on any reported thunderstorm")
    heavy_rain_mm_per_h: float = Field(gt=0)
    work_start_hour: int = Field(ge=0, le=23)
    work_end_hour: int = Field(ge=1, le=24, description="Exclusive")


class ScenarioConfig(Contract):
    name: str
    description: str
    timezone: str = "America/Chicago"
    planning_start: dt.date
    planning_end: dt.date
    evaluation_end: dt.date
    qualification_lag_days: Days = 0
    unscheduled_penalty_days: Days
    objective_policy: ObjectivePolicy = ObjectivePolicy.value_aware
    solve_time_limit_s: float = Field(default=15.0, gt=0)
    random_seed: int = 0
    num_workers: int = Field(default=8, ge=1)
    batteries: list[BatteryConfig]
    synthetic: bool
    provenance: list[ProvenanceNote]
    parameters: list[Parameter] = []
    weather_rule: WeatherRule | None = None
    min_gap_business_days: Days | None = Field(
        default=None, description="Business days from install to battery day. None means 1."
    )


class Scenario(Contract):
    scenario_id: Id
    scenario_hash: str
    revision: int = Field(default=0, ge=0)
    config: ScenarioConfig
    clusters: list[Cluster]
    sites: list[Site]
    crew_days: list[CrewDay]
    inventory: list[InventoryReceipt]
    current_plan: list[PlannedInstall]


class ScenarioSummary(Contract):
    scenario_id: Id
    name: str
    scenario_hash: str
    planning_start: dt.date
    planning_end: dt.date
    n_sites: int
    n_crews: int
    n_crew_days: int
    synthetic: bool


# --- Edits: disruptions (remove crew-day, delay inventory, change ready date)
# --- and interventions (add crew-day, force include) ----------------------


class RemoveCrewDay(Contract):
    kind: Literal["remove_crew_day"] = "remove_crew_day"
    crew_id: Id
    date: dt.date


class AddCrewDay(Contract):
    kind: Literal["add_crew_day"] = "add_crew_day"
    crew_id: Id
    date: dt.date
    available_min: Minutes
    skills: list[str]
    allowed_clusters: list[str]


class DelayInventory(Contract):
    kind: Literal["delay_inventory"] = "delay_inventory"
    configuration_id: Id
    from_date: dt.date
    to_date: dt.date
    quantity: int | None = Field(default=None, ge=0, description="None moves the whole receipt")


class ChangeReadyDate(Contract):
    kind: Literal["change_ready_date"] = "change_ready_date"
    site_id: Id
    ready_date: dt.date


class ForceInclude(Contract):
    kind: Literal["force_include"] = "force_include"
    site_id: Id


class ReduceCrewDay(Contract):
    """Disruption: reduced capacity. The crew-day keeps only available_min."""

    kind: Literal["reduce_crew_day"] = "reduce_crew_day"
    crew_id: Id
    date: dt.date
    available_min: Minutes


class ChangeAppointment(Contract):
    """Disruption: the customer can only host this visit inside the new window."""

    kind: Literal["change_appointment"] = "change_appointment"
    job_id: Id
    available_from: dt.date
    available_to: dt.date | None = None


class ExtendCrewDay(Contract):
    """Intervention: overtime. The crew-day gets extra minutes."""

    kind: Literal["extend_crew_day"] = "extend_crew_day"
    crew_id: Id
    date: dt.date
    extra_min: Minutes


class PinVisit(Contract):
    """Intervention: keep this visit on its current crew-day."""

    kind: Literal["pin_visit"] = "pin_visit"
    job_id: Id


class MoveVisit(Contract):
    """Intervention: put this visit on a chosen crew-day and keep it there."""

    kind: Literal["move_visit"] = "move_visit"
    job_id: Id
    crew_id: Id
    date: dt.date


# Disruptions: remove_crew_day (crew unavailable), reduce_crew_day, change_ready_date,
# change_appointment, delay_inventory. Interventions: add_crew_day (temporary capacity),
# extend_crew_day (overtime), pin_visit, move_visit, force_include.
Edit = Annotated[
    RemoveCrewDay
    | AddCrewDay
    | DelayInventory
    | ChangeReadyDate
    | ForceInclude
    | ReduceCrewDay
    | ChangeAppointment
    | ExtendCrewDay
    | PinVisit
    | MoveVisit,
    Field(discriminator="kind"),
]


# --- Plans ----------------------------------------------------------------


class PlanRequest(Contract):
    scenario_id: Id
    revision: int = Field(ge=0, description="Client edit counter, echoed in the result")
    edits: list[Edit] = []
    mode: Mode = Mode.strict
    algorithm: Algorithm = Algorithm.cpsat
    objective_policy: ObjectivePolicy | None = None
    time_limit_s: float | None = Field(default=None, gt=0)


class Assignment(Contract):
    site_id: Id
    crew_id: Id
    date: dt.date
    state: JobState
    days_late: Days = 0
    value_usd: Usd = 0.0
    job_id: str | None = Field(default=None, description="Visit job; None for one-visit homes")
    visit_type: VisitType | None = None


class UnscheduledJob(Contract):
    site_id: Id
    state: JobState
    reasons: list[ReasonCode]
    detail: str
    job_id: str | None = Field(default=None, description="None covers the whole home")
    visit_type: VisitType | None = None


class CrewDayUsage(Contract):
    crew_id: Id
    date: dt.date
    cluster_id: str | None
    onsite_min: Minutes
    travel_min: Minutes
    available_min: Minutes


class StageMeta(Contract):
    name: str
    status: StageStatus
    value: float | None = None
    bound: float | None = None
    gap: float | None = None
    elapsed_ms: int = Field(ge=0)


class ObjectiveComponents(Contract):
    jobs_on_time: int
    jobs_late: int
    jobs_unscheduled: int = Field(description="Includes blocked jobs")
    jobs_blocked: int
    total_delay_days: Days = Field(description="Sum of days late over assigned jobs")
    operating_value_usd: Usd
    changed_installs: int
    travel_allowance_min: Minutes
    crew_utilization: Fraction
    value_distinguishes_choices: bool
    visits_moved: int | None = Field(
        default=None, description="Planned visits moved or dropped. Same count as changed_installs"
    )
    customers_to_reschedule: int | None = Field(
        default=None, description="Distinct homes with at least one moved or dropped visit"
    )


class ValidationIssue(Contract):
    code: ViolationCode
    message: str
    site_id: str | None = None
    crew_id: str | None = None
    date: dt.date | None = None
    job_id: str | None = None


class ValidationReport(Contract):
    checked: bool = Field(description="False until the independent validator ran")
    valid: bool
    issues: list[ValidationIssue] = []
    validator: str


class Assumption(Contract):
    key: str
    text: str
    kind: DataKind


class InputIssue(Contract):
    code: InputIssueCode
    message: str
    file: str | None = None
    row: int | None = None


class PlanResult(Contract):
    plan_id: Id
    scenario_id: Id
    scenario_hash: str
    revision: int
    mode: Mode
    algorithm: Algorithm
    objective_policy: ObjectivePolicy
    edits: list[Edit]
    status: PlanStatus
    message: str = Field(description="One or two plain sentences for the operator")
    stages: list[StageMeta]
    assignments: list[Assignment]
    unscheduled: list[UnscheduledJob]
    crew_days: list[CrewDayUsage]
    objective: ObjectiveComponents | None
    validation: ValidationReport
    input_issues: list[InputIssue] = []
    assumptions: list[Assumption]
    solve_ms: int = Field(ge=0)


class Slot(Contract):
    crew_id: Id
    date: dt.date


class PlanChange(Contract):
    site_id: Id
    kind: ChangeKind
    before: Slot | None
    after: Slot | None
    before_state: JobState
    after_state: JobState
    note: str
    job_id: str | None = None
    visit_type: VisitType | None = None


class DiffSummary(Contract):
    moved: int
    added: int
    removed: int
    newly_late: int
    value_delta_usd: Usd
    travel_delta_min: int
    customers_to_reschedule: int | None = None


class CompareRequest(Contract):
    before: PlanResult
    after: PlanResult


class PlanDiff(Contract):
    before_plan_id: Id
    after_plan_id: Id
    changes: list[PlanChange]
    summary: DiffSummary
    headline: str


class CounterfactualRequest(Contract):
    request: PlanRequest = Field(description="The request that produced base")
    base: PlanResult
    intervention: Edit


class CounterfactualResult(Contract):
    intervention: Edit
    feasible: bool
    result: PlanResult
    diff: PlanDiff
    summary: str


class ApiError(Contract):
    code: str
    message: str
    input_issues: list[InputIssue] = []


# --- Data products ----------------------------------------------------------


class ValueTableRow(Contract):
    site_id: Id
    install_date: dt.date
    commissioning_utc: dt.datetime
    value_usd: Usd
    solver_status: str
    kind: DataKind
    input_hash: str


class Manifest(Contract):
    dataset_id: Id
    kind: DataKind
    source_url: str | None
    release: str | None
    retrieved_at: dt.datetime | None
    covered_start: dt.date | None
    covered_end: dt.date | None
    license_notes: str
    sha256: str
    transformation: str
    row_count: int
    fields: dict[str, DataKind]


# --- Recovery, storms, and season replay (contract 1.2; stubbed until lanes R and W land) ---


class RecoveryCounts(Contract):
    deadlines_missed: int
    deadlines_recovered: int = Field(description="Deadlines this option saves vs no action")
    delay_days: Days
    visits_moved: int
    customers_to_reschedule: int
    unscheduled: int


class EconomicLine(Contract):
    label: str
    amount_usd: Usd = Field(description="Positive is a cost, negative is a saving")
    kind: EconomicKind
    basis: str = Field(description="How the amount was computed, with its sources")


class RecoveryEconomics(Contract):
    net_impact_usd: Usd = Field(description="Modeled cost of this option vs the original plan")
    advantage_vs_no_action_usd: Usd = Field(description="No-action net impact minus this one")
    cost_per_deadline_recovered_usd: Usd | None = None
    lines: list[EconomicLine]


class Explanation(Contract):
    job_id: str
    text: str
    constraint: str


class CrewLoad(Contract):
    crew_id: Id
    date: dt.date
    before: Fraction
    after: Fraction


class RecoveryOption(Contract):
    option_id: Id
    kind: OptionKind
    action_label: str = Field(description='A business action, e.g. "Crew IB +2h overtime"')
    intervention_edits: list[Edit]
    status: PlanStatus
    proven_optimal: bool
    result: PlanResult
    diff_vs_original: PlanDiff
    diff_vs_no_action: PlanDiff | None
    counts: RecoveryCounts
    economics: RecoveryEconomics
    overtime_min: Minutes = 0
    explanations: list[Explanation]
    crew_load: list[CrewLoad]
    lowest_modeled_cost: bool = False
    stub: bool = False


class CascadeStep(Contract):
    """disruption -> directly affected visits -> battery days pushed -> commitments missed."""

    kind: CascadeKind
    label: str
    job_ids: list[str]


class ImpactAnalysis(Contract):
    headline: str
    affected_job_ids: list[str]
    lost_capacity_min: Minutes
    cascade: list[CascadeStep]
    deadlines_at_risk: int


class EconomicAssumption(Contract):
    key: str
    value: float
    unit: str
    kind: DataKind
    source: str
    editable: bool


class RecoveryOptionsRequest(Contract):
    scenario_id: Id
    revision: int = Field(ge=0)
    current_plan: list[PlannedInstall] | None = Field(
        default=None, description="None uses the scenario's current plan"
    )
    disruption: list[Edit]
    economics_overrides: dict[str, float] | None = None
    interactive: bool = False


class RecoveryOptionsResult(Contract):
    revision: int
    scenario_hash: str
    impact: ImpactAnalysis
    no_action: RecoveryOption
    options: list[RecoveryOption]
    economic_assumptions: list[EconomicAssumption]
    assumptions: list[Assumption]
    stub: bool = False


class EvaluateRequest(Contract):
    """Any manual change (knock out, stretch, drag, pin). Returns an option of kind custom."""

    scenario_id: Id
    revision: int = Field(ge=0)
    current_plan: list[PlannedInstall] | None = None
    disruption: list[Edit]
    interventions: list[Edit]
    interactive: bool = True


class ApproveRequest(Contract):
    scenario_id: Id
    revision: int = Field(ge=0)
    option: RecoveryOption


class ApproveResult(Contract):
    new_current_plan: list[PlannedInstall]
    summary: str
    stub: bool = False


class StormEvent(Contract):
    event_id: Id
    date: dt.date
    rainfall_mm: float = Field(ge=0, description="Work hours, 08:00-17:00 local")
    max_wind_kmh: float = Field(ge=0)
    thunder_hours: int = Field(ge=0)
    source: str
    stub: bool = False


class Case(Contract):
    case_id: Id
    name: str
    date: dt.date
    summary: str
    storm_event_id: str | None = None
    disruption: list[Edit]
    modeled_rule: str = Field(description="The modeled weather-to-disruption rule applied")
    provenance: list[ProvenanceNote]
    stub: bool = False


class SeasonReplayEvent(Contract):
    case_id: Id
    no_action: RecoveryCounts
    no_action_net_impact_usd: Usd
    recovery: RecoveryCounts
    recovery_net_impact_usd: Usd
    chosen_option_kind: OptionKind
    solve_ms: int = Field(ge=0)


class SeasonTotals(Contract):
    events_replayed: int
    deadline_misses_no_action: int
    deadline_misses_recovery: int
    deadlines_recovered: int
    modeled_cost_no_action_usd: Usd
    modeled_cost_recovery_usd: Usd
    median_solve_ms: int


class StressTest(Contract):
    variant: str
    deadlines_recovered: int
    advantage_usd: Usd


class SeasonReplay(Contract):
    replay_id: Id
    events: list[SeasonReplayEvent]
    totals: SeasonTotals
    stress_tests: list[StressTest] | None = None
    stub: bool = False
