"""SQLModel table definitions for the maluS v1 database (ADR 0001, ADR 0002).

The relational store replaces git as the canonical store: the frozen baseline
becomes an immutable :class:`DocumentVersion` (content hash), and RID
traceability becomes :class:`RidChange` links plus an append-only
:class:`AuditLog`.

Enum/status/type *values* are owned by ``malus.constants`` (the frozen domain
vocabulary); the columns here store those ``.value`` strings and the mapping
layer reconstructs the enum members. See ``docs/spec/data-model.md`` for the
normative schema and the ``rtd.yaml`` mapping.

Note: this module intentionally does not use ``from __future__ import
annotations`` — SQLModel resolves the real annotations at class-creation time to
build columns and relationships.
"""

import datetime as dt
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from malus.constants import Status


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class ReviewStatus(str, Enum):
    """Provisional review-level lifecycle.

    Step 1 needs only a stored, typed review status; the full phase model
    (freeze → harvest → triage → disposition → … → finalize) is refined by the
    API/lifecycle steps. Kept out of ``malus.constants`` so the frozen v0
    vocabulary is not touched.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    FINALIZED = "finalized"


class User(SQLModel, table=True):
    __tablename__ = "users"  # "user" is a reserved word in PostgreSQL

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    # Exact name string reproduced in rtd.yaml (owner / reviewer / verified_by).
    display_name: str
    email: Optional[str] = None
    # Set at Step 4 (argon2). Null for placeholder users created during import.
    password_hash: Optional[str] = None
    is_active: bool = True
    created: dt.datetime = Field(default_factory=_utcnow)


class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    id: Optional[int] = Field(default=None, primary_key=True)
    review_id_str: str = Field(unique=True, index=True)  # rtd meta.review_id
    title: Optional[str] = None
    # rtd meta.rid_prefix (optional; when absent it is derived from review_id).
    rid_prefix: Optional[str] = None
    owner_id: Optional[int] = Field(default=None, foreign_key="users.id", nullable=False)
    status: str = Field(default=ReviewStatus.DRAFT.value)
    created: dt.date = Field(default_factory=dt.date.today)  # rtd meta.created

    owner: Optional[User] = Relationship()
    documents: list["Document"] = Relationship(back_populates="review")
    reviewer_copies: list["ReviewerCopy"] = Relationship(back_populates="review")
    rids: list["RID"] = Relationship(back_populates="review")
    members: list["ReviewMember"] = Relationship(back_populates="review")


class ReviewMember(SQLModel, table=True):
    """A review-scoped role for a user (RBAC enforcement arrives at Step 4)."""

    __tablename__ = "review_members"
    __table_args__ = (UniqueConstraint("review_id", "user_id", name="uq_member_review_user"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    review_id: Optional[int] = Field(default=None, foreign_key="reviews.id", nullable=False)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", nullable=False)
    role: str  # Role.value: owner | reviewer | moderator

    review: Optional[Review] = Relationship(back_populates="members")
    user: Optional[User] = Relationship()


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    review_id: Optional[int] = Field(default=None, foreign_key="reviews.id", nullable=False)
    name: str  # rtd meta.document (path/name of the DUR)

    review: Optional[Review] = Relationship(back_populates="documents")
    versions: list["DocumentVersion"] = Relationship(back_populates="document")


class DocumentVersion(SQLModel, table=True):
    __tablename__ = "document_versions"

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: Optional[int] = Field(default=None, foreign_key="documents.id", nullable=False)
    ordinal: int
    content: str = ""
    # Immutable baseline identity; replaces the git baseline SHA. For a v1-native
    # version it is sha256(content); for a v0 import it preserves meta.baseline_sha.
    content_hash: str
    is_baseline: bool = False
    is_final: bool = False
    created_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created: dt.datetime = Field(default_factory=_utcnow)

    document: Optional[Document] = Relationship(back_populates="versions")
    created_by: Optional[User] = Relationship()


class ReviewerCopy(SQLModel, table=True):
    """One per (review, reviewer); replaces ``reviewers/<name>.md``."""

    __tablename__ = "reviewer_copies"
    __table_args__ = (UniqueConstraint("review_id", "user_id", name="uq_copy_review_user"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    review_id: Optional[int] = Field(default=None, foreign_key="reviews.id", nullable=False)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", nullable=False)
    based_on_version_id: Optional[int] = Field(
        default=None, foreign_key="document_versions.id"
    )
    content: str = ""
    submitted_at: Optional[dt.datetime] = None

    review: Optional[Review] = Relationship(back_populates="reviewer_copies")
    user: Optional[User] = Relationship()
    based_on_version: Optional[DocumentVersion] = Relationship()


class RID(SQLModel, table=True):
    """A single Review Item Discrepancy; mirrors the frozen v0 RID schema.

    ``duplicates`` is not stored: it is the inverse of ``master_id`` (the
    adjacency-list self relationship below).
    """

    __tablename__ = "rids"
    __table_args__ = (UniqueConstraint("review_id", "rid_str", name="uq_rid_review_ridstr"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    review_id: Optional[int] = Field(default=None, foreign_key="reviews.id", nullable=False)
    rid_str: str = Field(index=True)  # stable <PROJECT>-<DOC>-<NNNN>
    reviewer_id: Optional[int] = Field(default=None, foreign_key="users.id", nullable=False)
    created: dt.date = Field(default_factory=dt.date.today)
    anchor_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    kind: str  # Kind.value (COMM | SUGG)
    type: Optional[str] = None  # CommentType.value | None
    severity: Optional[str] = None  # Severity.value | None
    status: str = Field(default=Status.OPEN.value)  # Status.value
    comment: Optional[str] = None
    reply: Optional[str] = None
    disposition: Optional[str] = None  # Disposition.value | None
    resolution: Optional[str] = None
    master_id: Optional[int] = Field(default=None, foreign_key="rids.id")
    verified_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    verified_on: Optional[dt.date] = None
    ai_drafted: bool = False

    review: Optional[Review] = Relationship(back_populates="rids")
    reviewer: Optional[User] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[RID.reviewer_id]"}
    )
    verified_by: Optional[User] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[RID.verified_by_id]"}
    )
    master: Optional["RID"] = Relationship(
        back_populates="duplicates",
        sa_relationship_kwargs={"remote_side": "RID.id"},
    )
    duplicates: list["RID"] = Relationship(back_populates="master")
    changes: list["RidChange"] = Relationship(back_populates="rid")


class RidChange(SQLModel, table=True):
    """Links an implementation edit (a version) to the RID it resolves;
    replaces "RID id in the commit message"."""

    __tablename__ = "rid_changes"

    id: Optional[int] = Field(default=None, primary_key=True)
    rid_id: Optional[int] = Field(default=None, foreign_key="rids.id", nullable=False)
    version_id: Optional[int] = Field(
        default=None, foreign_key="document_versions.id", nullable=False
    )
    note: Optional[str] = None

    rid: Optional[RID] = Relationship(back_populates="changes")
    version: Optional[DocumentVersion] = Relationship()


class AuditLog(SQLModel, table=True):
    """Append-only record of every state-changing action; the traceability spine."""

    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    actor_id: Optional[int] = Field(default=None, foreign_key="users.id")
    action: str
    target: str
    detail_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    ts: dt.datetime = Field(default_factory=_utcnow)

    actor: Optional[User] = Relationship()
