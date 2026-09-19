# packages/storage/tests/test_state_machine.py
import pytest

from fathomark_storage.state_machine import InvalidTransition, RunState, transition


def test_happy_path_created_to_approved():
    s = RunState.CREATED
    for target in (
        RunState.COLLECTING,
        RunState.ANALYZING,
        RunState.DRAFT,
        RunState.APPROVED,
    ):
        s = transition(s, target)
    assert s == RunState.APPROVED


def test_approve_only_from_draft():
    with pytest.raises(InvalidTransition):
        transition(RunState.COLLECTING, RunState.APPROVED)


def test_approved_is_terminal_except_superseded():
    with pytest.raises(InvalidTransition):
        transition(RunState.APPROVED, RunState.DRAFT)
    assert transition(RunState.APPROVED, RunState.SUPERSEDED) == RunState.SUPERSEDED


def test_cancelled_is_terminal():
    with pytest.raises(InvalidTransition):
        transition(RunState.CANCELLED, RunState.COLLECTING)


def test_needs_review_resolves_to_draft():
    assert transition(RunState.DRAFT, RunState.NEEDS_REVIEW) == RunState.NEEDS_REVIEW
    assert transition(RunState.NEEDS_REVIEW, RunState.DRAFT) == RunState.DRAFT
