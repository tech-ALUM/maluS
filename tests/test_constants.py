"""Tests for the frozen domain vocabulary and the transition table."""

from malus.constants import (
    DEFAULT_SEVERITY,
    DEFAULT_TYPE,
    TERMINAL_STATUSES,
    TRANSITIONS,
    CommentType,
    Severity,
    Status,
    is_allowed_transition,
)


def test_comment_type_has_four_values_including_process() -> None:
    assert {t.value for t in CommentType} == {"typo", "editorial", "technical", "process"}


def test_severity_values() -> None:
    assert {s.value for s in Severity} == {"minor", "major", "critical"}


def test_status_values() -> None:
    assert {s.value for s in Status} == {
        "open",
        "answered",
        "implemented",
        "verified",
        "withdrawn",
    }


def test_comm_defaults_match_spec() -> None:
    assert DEFAULT_TYPE is CommentType.EDITORIAL
    assert DEFAULT_SEVERITY is Severity.MINOR


def test_transition_graph_matches_spec() -> None:
    assert TRANSITIONS[Status.OPEN] == frozenset({Status.ANSWERED, Status.WITHDRAWN})
    assert TRANSITIONS[Status.ANSWERED] == frozenset({Status.IMPLEMENTED, Status.VERIFIED})
    assert TRANSITIONS[Status.IMPLEMENTED] == frozenset({Status.VERIFIED})
    assert TRANSITIONS[Status.VERIFIED] == frozenset()
    assert TRANSITIONS[Status.WITHDRAWN] == frozenset()


def test_terminal_statuses() -> None:
    assert TERMINAL_STATUSES == frozenset({Status.VERIFIED, Status.WITHDRAWN})


def test_is_allowed_transition() -> None:
    assert is_allowed_transition(Status.OPEN, Status.ANSWERED)
    assert is_allowed_transition(Status.IMPLEMENTED, Status.VERIFIED)
    assert not is_allowed_transition(Status.OPEN, Status.VERIFIED)
    assert not is_allowed_transition(Status.VERIFIED, Status.OPEN)
