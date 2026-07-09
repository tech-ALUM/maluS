"""Frozen domain vocabulary and the status-transition table.

This module is the single source of truth for the review enumerations and
the status lifecycle, shared by the CLI and the GUI. The normative contracts
are ``docs/spec/comment-syntax.md`` and ``docs/spec/rid-schema.md``.
"""

from __future__ import annotations

from enum import Enum


class Kind(str, Enum):
    """Whether a RID is a discussion comment or a mechanical suggestion."""

    COMM = "COMM"
    SUGG = "SUGG"


class CommentType(str, Enum):
    """The ``type`` of a ``{COMM}`` finding (comment-syntax.md §2)."""

    TYPO = "typo"
    EDITORIAL = "editorial"
    TECHNICAL = "technical"
    PROCESS = "process"


class Severity(str, Enum):
    """The ``sev`` of a ``{COMM}`` finding (comment-syntax.md §2)."""

    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class Status(str, Enum):
    """A RID's lifecycle state (rid-schema.md §3)."""

    OPEN = "open"
    ANSWERED = "answered"
    IMPLEMENTED = "implemented"
    VERIFIED = "verified"
    WITHDRAWN = "withdrawn"


class Disposition(str, Enum):
    """The owner's decision on a RID (rid-schema.md §1)."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class Role(str, Enum):
    """The seat an actor occupies. A seat may be filled by a human or an AI."""

    OWNER = "owner"
    REVIEWER = "reviewer"
    MODERATOR = "moderator"


# Defaults applied to a ``{COMM}`` when a parameter is omitted (comment-syntax.md §2).
DEFAULT_TYPE: CommentType = CommentType.EDITORIAL
DEFAULT_SEVERITY: Severity = Severity.MINOR

# Status transition graph (rid-schema.md §3). The single source of truth for
# which status changes are structurally permitted; actor-authority rules are
# enforced on top of this in ``malus.models.transition``.
TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.OPEN: frozenset({Status.ANSWERED, Status.WITHDRAWN}),
    Status.ANSWERED: frozenset({Status.IMPLEMENTED, Status.VERIFIED}),
    Status.IMPLEMENTED: frozenset({Status.VERIFIED}),
    Status.VERIFIED: frozenset(),
    Status.WITHDRAWN: frozenset(),
}

# States from which no further transition is possible.
TERMINAL_STATUSES: frozenset[Status] = frozenset({Status.VERIFIED, Status.WITHDRAWN})


def is_allowed_transition(current: Status, target: Status) -> bool:
    """Return ``True`` if ``current -> target`` is in the status graph."""
    return target in TRANSITIONS.get(current, frozenset())
