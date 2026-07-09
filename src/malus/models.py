"""Dataclasses for the RTD (``rtd.yaml``) with YAML round-trip helpers.

See ``docs/spec/rid-schema.md`` for the normative schema. Serialization
preserves the schema key order and emits plain scalars so that GUI/CLI saves
produce minimal git diffs.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

import yaml

from .constants import (
    CommentType,
    Disposition,
    Kind,
    Role,
    Severity,
    Status,
    is_allowed_transition,
)

_E = TypeVar("_E", bound=Enum)


class _NoAliasDumper(yaml.SafeDumper):
    """SafeDumper that never emits YAML anchors/aliases, for stable git diffs."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


def _represent_str(dumper: Any, data: str) -> Any:
    # Force multi-line strings onto a single double-quoted line so the GUI's
    # line-oriented reader never has to parse block scalars; single-line strings
    # keep PyYAML's default style, so existing output is unchanged.
    style = '"' if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_NoAliasDumper.add_representer(str, _represent_str)


def _as_date(value: Any) -> _dt.date | None:
    """Coerce a YAML scalar to a ``date`` (accepts ``date``/``datetime``/ISO string)."""
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, str):
        return _dt.date.fromisoformat(value)
    raise TypeError(f"cannot interpret {value!r} as a date")


def _to_enum(enum_cls: type[_E], value: Any) -> _E | None:
    """Build an enum member from its value, passing ``None`` through."""
    if value is None:
        return None
    return enum_cls(value)


@dataclass
class Anchor:
    """Location context for a finding (comment-syntax.md §5)."""

    section: str | None = None
    quote: str | None = None
    line_hint: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"section": self.section, "quote": self.quote, "line_hint": self.line_hint}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Anchor:
        data = data or {}
        return cls(
            section=data.get("section"),
            quote=data.get("quote"),
            line_hint=data.get("line_hint"),
        )


@dataclass
class RID:
    """A single Review Item Discrepancy (rid-schema.md §1)."""

    rid: str
    reviewer: str
    created: _dt.date
    kind: Kind
    anchor: Anchor = field(default_factory=Anchor)
    type: CommentType | None = None
    severity: Severity | None = None
    status: Status = Status.OPEN
    comment: str | None = None
    reply: str | None = None
    disposition: Disposition | None = None
    resolution: str | None = None
    master: str | None = None
    duplicates: list[str] = field(default_factory=list)
    verified_by: str | None = None
    verified_on: _dt.date | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize in the normative schema key order (rid-schema.md §1)."""
        return {
            "rid": self.rid,
            "reviewer": self.reviewer,
            "created": self.created,
            "anchor": self.anchor.to_dict(),
            "kind": self.kind.value,
            "type": None if self.type is None else self.type.value,
            "severity": None if self.severity is None else self.severity.value,
            "status": self.status.value,
            "comment": self.comment,
            "reply": self.reply,
            "disposition": None if self.disposition is None else self.disposition.value,
            "resolution": self.resolution,
            "master": self.master,
            "duplicates": list(self.duplicates),
            "verified_by": self.verified_by,
            "verified_on": self.verified_on,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RID:
        return cls(
            rid=data["rid"],
            reviewer=data["reviewer"],
            created=_as_date(data.get("created")),
            kind=Kind(data["kind"]),
            anchor=Anchor.from_dict(data.get("anchor")),
            type=_to_enum(CommentType, data.get("type")),
            severity=_to_enum(Severity, data.get("severity")),
            status=Status(data.get("status", Status.OPEN.value)),
            comment=data.get("comment"),
            reply=data.get("reply"),
            disposition=_to_enum(Disposition, data.get("disposition")),
            resolution=data.get("resolution"),
            master=data.get("master"),
            duplicates=list(data.get("duplicates") or []),
            verified_by=data.get("verified_by"),
            verified_on=_as_date(data.get("verified_on")),
        )


@dataclass
class Meta:
    """The ``meta:`` header of an ``rtd.yaml`` (rid-schema.md §1)."""

    review_id: str
    document: str
    baseline_sha: str
    created: _dt.date
    owner: str
    reviewers: list[str] = field(default_factory=list)
    rid_prefix: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"review_id": self.review_id}
        if self.rid_prefix is not None:
            data["rid_prefix"] = self.rid_prefix
        data.update(
            {
                "document": self.document,
                "baseline_sha": self.baseline_sha,
                "created": self.created,
                "owner": self.owner,
                "reviewers": list(self.reviewers),
            }
        )
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Meta:
        return cls(
            review_id=data["review_id"],
            document=data["document"],
            baseline_sha=data["baseline_sha"],
            created=_as_date(data.get("created")),
            owner=data["owner"],
            reviewers=list(data.get("reviewers") or []),
            rid_prefix=data.get("rid_prefix"),
        )


@dataclass
class RTD:
    """The whole Revision Tracking Document: ``meta`` header + ``rids`` list."""

    meta: Meta
    rids: list[RID] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"meta": self.meta.to_dict(), "rids": [r.to_dict() for r in self.rids]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RTD:
        return cls(
            meta=Meta.from_dict(data["meta"]),
            rids=[RID.from_dict(r) for r in (data.get("rids") or [])],
        )

    def to_yaml(self) -> str:
        """Render to YAML with stable key order and plain scalars."""
        return yaml.dump(
            self.to_dict(),
            Dumper=_NoAliasDumper,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=1_000_000,  # never wrap scalars, so every value stays on one line
        )

    @classmethod
    def from_yaml(cls, text: str) -> RTD:
        return cls.from_dict(yaml.safe_load(text))


class TransitionError(ValueError):
    """Raised when a status transition is structurally illegal or unauthorized."""


def transition(
    rid: RID,
    target: Status,
    *,
    actor_role: Role,
    actor_name: str | None = None,
    actor_is_ai: bool = False,
    on: _dt.date | None = None,
) -> None:
    """Move ``rid`` to ``target`` in place, enforcing the lifecycle rules.

    Two independent gates must pass (rid-schema.md §3):

    1. **Status graph** — ``rid.status -> target`` must be in
       :data:`malus.constants.TRANSITIONS`.
    2. **Actor authority** — the closure-authority invariant (D3):

       * only the RID's own reviewer, or a moderator on their behalf, may set
         ``verified``; the owner never may, and an AI never may regardless of
         seat;
       * only the RID's own reviewer may ``withdraw`` (from ``open`` only,
         which the status graph already enforces).

    On a successful verify the RID is stamped with ``verified_by``/
    ``verified_on``. Raises :class:`TransitionError` without mutating ``rid``
    when either gate fails.
    """
    if not is_allowed_transition(rid.status, target):
        raise TransitionError(
            f"illegal transition {rid.status.value} -> {target.value}"
        )

    if target is Status.VERIFIED:
        if actor_is_ai:
            raise TransitionError(
                "an AI may never set 'verified' (closure-authority invariant)"
            )
        if actor_role is Role.OWNER:
            raise TransitionError(
                "the owner may never set 'verified'; closure belongs to the reviewer"
            )
        if (
            actor_role is Role.REVIEWER
            and actor_name is not None
            and actor_name != rid.reviewer
        ):
            raise TransitionError(
                f"reviewer {actor_name!r} may not verify a RID owned by {rid.reviewer!r}"
            )

    if target is Status.WITHDRAWN:
        if actor_role is not Role.REVIEWER or (
            actor_name is not None and actor_name != rid.reviewer
        ):
            raise TransitionError("only the RID's own reviewer may withdraw it")

    rid.status = target
    if target is Status.VERIFIED:
        rid.verified_by = actor_name
        rid.verified_on = on
