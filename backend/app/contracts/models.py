import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.enums import (
    Algorithm,
    ChangeKind,
    DataKind,
    InputIssueCode,
    JobState,
    Mode,
    ObjectivePolicy,
    PlanStatus,
    ReasonCode,
    StageStatus,
    ViolationCode,
)
from app.contracts.units import KW, Days, Fraction, Id, KWh, Minutes, Usd

CONTRACT_VERSION = "1.0.0"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


# --- Inputs ---------------------------------------------------------------


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


Edit = Annotated[
    RemoveCrewDay | AddCrewDay | DelayInventory | ChangeReadyDate | ForceInclude,
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


class UnscheduledJob(Contract):
    site_id: Id
    state: JobState
    reasons: list[ReasonCode]
    detail: str


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


class ValidationIssue(Contract):
    code: ViolationCode
    message: str
    site_id: str | None = None
    crew_id: str | None = None
    date: dt.date | None = None


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


class DiffSummary(Contract):
    moved: int
    added: int
    removed: int
    newly_late: int
    value_delta_usd: Usd
    travel_delta_min: int


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
