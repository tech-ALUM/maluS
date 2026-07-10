"""Typed request/response models for the HTTP API.

Response models are built from the domain objects (DB rows and the ``RTD``
dataclasses returned by the services), so the wire shape is decoupled from the
ORM and mirrors the frozen RID schema (``docs/spec/rid-schema.md``).
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

from pydantic import BaseModel

from malus.models import RID as RidDTO


# --------------------------------------------------------------------------- #
# requests
# --------------------------------------------------------------------------- #


class ReviewCreate(BaseModel):
    review_id: str
    document_name: str = "baseline.md"
    owner: str
    reviewers: list[str] = []
    title: Optional[str] = None
    rid_prefix: Optional[str] = None
    created: Optional[dt.date] = None


class DocumentIn(BaseModel):
    content: str


class ReviewerAdd(BaseModel):
    name: str


class CopyIn(BaseModel):
    content: str


class FreezeIn(BaseModel):
    content: Optional[str] = None  # defaults to the current document content


class TriageIn(BaseModel):
    auto: bool = False
    threshold: float = 0.6
    auto_threshold: float = 0.82


class ApplySuggsIn(BaseModel):
    dry_run: bool = False


class RidPatch(BaseModel):
    reply: Optional[str] = None
    disposition: Optional[str] = None  # accepted | rejected | deferred
    resolution: Optional[str] = None
    status: Optional[str] = None  # answered | implemented (verify/reopen have their own routes)


class VerifyIn(BaseModel):
    reviewer: str
    moderator: bool = False


class ReopenIn(BaseModel):
    reviewer: str
    reason: str
    moderator: bool = False


class ChangeIn(BaseModel):
    content: str  # the edited document version
    rids: list[str]  # the RIDs this edit resolves
    note: Optional[str] = None


# --------------------------------------------------------------------------- #
# responses
# --------------------------------------------------------------------------- #


class AnchorOut(BaseModel):
    section: Optional[str] = None
    quote: Optional[str] = None
    line_hint: Optional[int] = None


class RidOut(BaseModel):
    rid: str
    reviewer: str
    created: dt.date
    anchor: AnchorOut
    kind: str
    type: Optional[str] = None
    severity: Optional[str] = None
    status: str
    comment: Optional[str] = None
    reply: Optional[str] = None
    disposition: Optional[str] = None
    resolution: Optional[str] = None
    master: Optional[str] = None
    duplicates: list[str] = []
    verified_by: Optional[str] = None
    verified_on: Optional[dt.date] = None
    ai_drafted: bool = False

    @classmethod
    def from_dto(cls, r: RidDTO) -> "RidOut":
        return cls(
            rid=r.rid,
            reviewer=r.reviewer,
            created=r.created,
            anchor=AnchorOut(**r.anchor.to_dict()),
            kind=r.kind.value,
            type=r.type.value if r.type else None,
            severity=r.severity.value if r.severity else None,
            status=r.status.value,
            comment=r.comment,
            reply=r.reply,
            disposition=r.disposition.value if r.disposition else None,
            resolution=r.resolution,
            master=r.master,
            duplicates=list(r.duplicates),
            verified_by=r.verified_by,
            verified_on=r.verified_on,
            ai_drafted=r.ai_drafted,
        )


class ReviewOut(BaseModel):
    review_id: str
    title: Optional[str] = None
    rid_prefix: Optional[str] = None
    owner: str
    status: str
    created: dt.date
    reviewers: list[str] = []
    document: str

    @classmethod
    def from_row(cls, review) -> "ReviewOut":
        from malus.constants import Role

        reviewers = [
            m.user.display_name
            for m in sorted(review.members, key=lambda m: m.id)
            if m.role == Role.REVIEWER.value
        ]
        document = review.documents[0].name if review.documents else ""
        return cls(
            review_id=review.review_id_str,
            title=review.title,
            rid_prefix=review.rid_prefix,
            owner=review.owner.display_name,
            status=review.status,
            created=review.created,
            reviewers=reviewers,
            document=document,
        )


class VersionOut(BaseModel):
    ordinal: int
    content_hash: str
    is_baseline: bool
    is_final: bool

    @classmethod
    def from_row(cls, v) -> "VersionOut":
        return cls(
            ordinal=v.ordinal,
            content_hash=v.content_hash,
            is_baseline=v.is_baseline,
            is_final=v.is_final,
        )


class DocumentOut(BaseModel):
    name: str
    content: str
    version: Optional[VersionOut] = None


class CopyOut(BaseModel):
    user: str
    content: str
    based_on_ordinal: Optional[int] = None


class ViolationOut(BaseModel):
    reviewer: str
    message: str
    line: Optional[int] = None


class HarvestOut(BaseModel):
    rids: list[RidOut]
    violations: list[ViolationOut]


class DuplicateLinkOut(BaseModel):
    duplicate: str
    confidence: float


class ClusterOut(BaseModel):
    master: str
    links: list[DuplicateLinkOut]


class TriageOut(BaseModel):
    proposals: list[ClusterOut]
    applied: int


class SuggResultOut(BaseModel):
    rid: str
    old: str
    new: str
    applied: bool
    reason: str = ""


class ApplySuggsOut(BaseModel):
    version: Optional[VersionOut] = None  # null on dry_run
    results: list[SuggResultOut]


class ChangeOut(BaseModel):
    version: VersionOut
    linked: list[str]


class TraceabilityOut(BaseModel):
    referenced: dict[str, list[str]]
    accepted_unreferenced: list[str]
    referenced_not_accepted: list[str]
    ok: bool


class ReportOut(BaseModel):
    errors: list[str]
    report: str


class FinalizeOut(BaseModel):
    errors: list[str]
    finalized: bool
    status: str
