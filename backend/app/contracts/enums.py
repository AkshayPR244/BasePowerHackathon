from enum import StrEnum


class PlanStatus(StrEnum):
    optimal = "optimal"
    feasible = "feasible"
    infeasible = "infeasible"
    timeout_no_incumbent = "timeout_no_incumbent"
    invalid_input = "invalid_input"


class StageStatus(StrEnum):
    optimal = "optimal"
    feasible = "feasible"
    infeasible = "infeasible"
    timeout_no_incumbent = "timeout_no_incumbent"
    skipped = "skipped"


class Mode(StrEnum):
    strict = "strict"
    recovery = "recovery"


class Algorithm(StrEnum):
    cpsat = "cpsat"
    baseline_edf = "baseline_edf"
    baseline_nearest_cluster = "baseline_nearest_cluster"


class ObjectivePolicy(StrEnum):
    value_aware = "value_aware"
    deadline_travel_only = "deadline_travel_only"


class VisitType(StrEnum):
    install = "install"
    battery_day = "battery_day"


class ReasonCode(StrEnum):
    NOT_READY = "NOT_READY"
    SKILL_MISMATCH = "SKILL_MISMATCH"
    CLUSTER_NOT_ALLOWED = "CLUSTER_NOT_ALLOWED"
    NO_LEGAL_DATE = "NO_LEGAL_DATE"
    NO_INVENTORY = "NO_INVENTORY"
    CAPACITY = "CAPACITY"
    LOCK_CONFLICT = "LOCK_CONFLICT"
    DEADLINE_BEFORE_READY = "DEADLINE_BEFORE_READY"


class JobState(StrEnum):
    scheduled = "scheduled"
    locked = "locked"
    late = "late"
    unscheduled = "unscheduled"
    blocked = "blocked"


class DataKind(StrEnum):
    observed = "observed"
    modeled = "modeled"
    derived = "derived"
    assumed = "assumed"
    synthetic = "synthetic"


class ViolationCode(StrEnum):
    UNKNOWN_SITE = "UNKNOWN_SITE"
    DUPLICATE_ASSIGNMENT = "DUPLICATE_ASSIGNMENT"
    NO_CREW_DAY = "NO_CREW_DAY"
    BEFORE_READY = "BEFORE_READY"
    AFTER_DEADLINE = "AFTER_DEADLINE"
    MISSING_JOB = "MISSING_JOB"
    SKILL = "SKILL"
    CLUSTER_NOT_ALLOWED = "CLUSTER_NOT_ALLOWED"
    MULTIPLE_CLUSTERS = "MULTIPLE_CLUSTERS"
    CAPACITY = "CAPACITY"
    INVENTORY = "INVENTORY"
    LOCK_BROKEN = "LOCK_BROKEN"
    STATE_MISMATCH = "STATE_MISMATCH"
    OBJECTIVE_MISMATCH = "OBJECTIVE_MISMATCH"
    PRECEDENCE = "PRECEDENCE"


class InputIssueCode(StrEnum):
    DUPLICATE_ID = "DUPLICATE_ID"
    UNKNOWN_REFERENCE = "UNKNOWN_REFERENCE"
    BAD_VALUE = "BAD_VALUE"
    DATE_ORDER = "DATE_ORDER"
    DUPLICATE_PLANNED_INSTALL = "DUPLICATE_PLANNED_INSTALL"
    CONTRADICTORY_LOCKS = "CONTRADICTORY_LOCKS"
    MISSING_INTERVAL = "MISSING_INTERVAL"
    MISSING_FILE = "MISSING_FILE"


class ChangeKind(StrEnum):
    added = "added"
    removed = "removed"
    moved = "moved"
    state_changed = "state_changed"


class OptionKind(StrEnum):
    no_action = "no_action"
    rebalance = "rebalance"
    overtime = "overtime"
    temporary_capacity = "temporary_capacity"
    custom = "custom"


class CascadeKind(StrEnum):
    disruption = "disruption"
    direct = "direct"
    pushed = "pushed"
    commitment = "commitment"


class EconomicKind(StrEnum):
    labor = "labor"
    value = "value"
    penalty = "penalty"
    other = "other"
