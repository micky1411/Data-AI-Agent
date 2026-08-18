"""Incident domain model and valid state transitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IncidentState(StrEnum):
    DETECTED = "DETECTED"
    COLLECTING = "COLLECTING"
    INVESTIGATING = "INVESTIGATING"
    AUTO_RECOVERING = "AUTO_RECOVERING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    NOTIFY_ONLY = "NOTIFY_ONLY"
    VALIDATING = "VALIDATING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


ALLOWED_TRANSITIONS: dict[IncidentState, frozenset[IncidentState]] = {
    IncidentState.DETECTED: frozenset({IncidentState.COLLECTING}),
    IncidentState.COLLECTING: frozenset({IncidentState.INVESTIGATING}),
    IncidentState.INVESTIGATING: frozenset({
        IncidentState.AUTO_RECOVERING,
        IncidentState.AWAITING_APPROVAL,
        IncidentState.NOTIFY_ONLY,
        IncidentState.ESCALATED,
    }),
    IncidentState.AUTO_RECOVERING: frozenset({IncidentState.VALIDATING, IncidentState.ESCALATED}),
    IncidentState.AWAITING_APPROVAL: frozenset({IncidentState.VALIDATING, IncidentState.ESCALATED}),
    IncidentState.NOTIFY_ONLY: frozenset({IncidentState.RESOLVED, IncidentState.ESCALATED}),
    IncidentState.VALIDATING: frozenset({IncidentState.RESOLVED, IncidentState.ESCALATED}),
    IncidentState.RESOLVED: frozenset(),
    IncidentState.ESCALATED: frozenset(),
}


class InvalidTransition(ValueError):
    """Raised when an incident state change violates the state machine."""


def require_transition(current: IncidentState, target: IncidentState) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"invalid incident transition {current} -> {target}")


@dataclass(frozen=True)
class FailureEvent:
    dag_id: str
    task_id: str
    run_id: str
    try_number: int
    logical_date: str | None
    exception: str
    log_url: str
