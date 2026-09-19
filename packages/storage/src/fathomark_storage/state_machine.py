"""Research-run state machine. Spec: design doc section 9."""

from enum import StrEnum


class RunState(StrEnum):
    CREATED = "created"
    SCOPED = "scoped"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    AUDITING = "auditing"
    NEEDS_REVIEW = "needs_review"
    DRAFT = "draft"
    APPROVED = "approved"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


TERMINAL_STATES = frozenset(
    {RunState.APPROVED, RunState.FAILED, RunState.CANCELLED, RunState.SUPERSEDED}
)

TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.CREATED: frozenset(
        {RunState.SCOPED, RunState.COLLECTING, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.SCOPED: frozenset(
        {RunState.COLLECTING, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.COLLECTING: frozenset(
        {RunState.ANALYZING, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.ANALYZING: frozenset(
        {
            RunState.AUDITING,
            RunState.DRAFT,
            RunState.NEEDS_REVIEW,
            RunState.CANCELLED,
            RunState.FAILED,
        }
    ),
    RunState.AUDITING: frozenset(
        {RunState.DRAFT, RunState.NEEDS_REVIEW, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.NEEDS_REVIEW: frozenset(
        {RunState.ANALYZING, RunState.DRAFT, RunState.CANCELLED, RunState.FAILED}
    ),
    RunState.DRAFT: frozenset(
        {RunState.APPROVED, RunState.NEEDS_REVIEW, RunState.CANCELLED}
    ),
    RunState.APPROVED: frozenset({RunState.SUPERSEDED}),
    RunState.FAILED: frozenset({RunState.COLLECTING, RunState.CANCELLED}),
    RunState.CANCELLED: frozenset(),
    RunState.SUPERSEDED: frozenset(),
}


class InvalidTransition(ValueError):
    def __init__(self, current: RunState, target: RunState):
        super().__init__(f"illegal transition {current} -> {target}")
        self.current = current
        self.target = target


def transition(current: RunState, target: RunState) -> RunState:
    if target not in TRANSITIONS[current]:
        raise InvalidTransition(current, target)
    return target
