"""Repository classes wrapping a SQLModel ``Session`` (v1 Step 2, ADR 0001).

Repositories are the only place that reads/writes rows; the reused domain core
and the services above them never touch the session directly. Repos flush (to
assign ids) but never commit — the caller owns the transaction boundary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, select

from malus.db.models import (
    RID,
    AuditLog,
    Document,
    DocumentVersion,
    Review,
    ReviewerCopy,
    ReviewMember,
    ReviewStatus,
    RidChange,
    User,
)


def content_hash(text: str) -> str:
    """The immutable version identity: sha256 of the UTF-8 content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class UserRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def by_username(self, username: str) -> Optional[User]:
        return self.s.exec(select(User).where(User.username == username)).first()

    def by_display_name(self, name: str) -> Optional[User]:
        return self.s.exec(select(User).where(User.display_name == name)).first()

    def get_or_create(self, display_name: str, *, username: Optional[str] = None) -> User:
        user = self.by_display_name(display_name)
        if user is None:
            user = User(username=username or display_name, display_name=display_name)
            self.s.add(user)
            self.s.flush()
        return user


class ReviewRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def create(
        self,
        review_id: str,
        *,
        owner: User,
        document_name: str,
        title: Optional[str] = None,
        rid_prefix: Optional[str] = None,
        created: Optional[dt.date] = None,
        status: str = ReviewStatus.DRAFT.value,
    ) -> Review:
        review = Review(
            review_id_str=review_id,
            title=title,
            rid_prefix=rid_prefix,
            owner=owner,
            status=status,
            created=created or dt.date.today(),
        )
        self.s.add(review)
        self.s.flush()
        self.s.add(Document(review=review, name=document_name))
        self.s.flush()
        return review

    def get(self, review_id: str) -> Optional[Review]:
        return self.s.exec(select(Review).where(Review.review_id_str == review_id)).first()

    def get_by_id(self, review_id: int) -> Optional[Review]:
        return self.s.get(Review, review_id)

    def list(self) -> list[Review]:
        return list(self.s.exec(select(Review).order_by(Review.id)).all())

    def add_member(self, review: Review, user: User, role: str) -> ReviewMember:
        member = ReviewMember(review=review, user=user, role=role)
        self.s.add(member)
        self.s.flush()
        return member

    def set_status(self, review: Review, status: str) -> None:
        review.status = status
        self.s.add(review)
        self.s.flush()


class VersionRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def _document(self, review: Review) -> Document:
        return review.documents[0]

    def _next_ordinal(self, document: Document) -> int:
        current = self.s.exec(
            select(func.max(DocumentVersion.ordinal)).where(
                DocumentVersion.document_id == document.id
            )
        ).one()
        return (current or 0) + 1

    def freeze(self, review: Review, content: str, *, by: Optional[User] = None) -> DocumentVersion:
        """Create the immutable, hash-pinned baseline version."""
        document = self._document(review)
        version = DocumentVersion(
            document=document,
            ordinal=self._next_ordinal(document),
            content=content,
            content_hash=content_hash(content),
            is_baseline=True,
            created_by=by,
        )
        self.s.add(version)
        self.s.flush()
        return version

    def add_version(
        self,
        review: Review,
        content: str,
        *,
        by: Optional[User] = None,
        is_final: bool = False,
    ) -> DocumentVersion:
        document = self._document(review)
        version = DocumentVersion(
            document=document,
            ordinal=self._next_ordinal(document),
            content=content,
            content_hash=content_hash(content),
            is_final=is_final,
            created_by=by,
        )
        self.s.add(version)
        self.s.flush()
        return version

    def baseline(self, review: Review) -> Optional[DocumentVersion]:
        return self.s.exec(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == self._document(review).id)
            .where(DocumentVersion.is_baseline == True)  # noqa: E712 (SQL comparison)
        ).first()

    def latest(self, review: Review) -> Optional[DocumentVersion]:
        return self.s.exec(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == self._document(review).id)
            .order_by(DocumentVersion.ordinal.desc())
        ).first()


class ReviewerCopyRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def upsert(
        self,
        review: Review,
        user: User,
        content: str,
        *,
        based_on: Optional[DocumentVersion] = None,
        submitted_at: Optional[dt.datetime] = None,
    ) -> ReviewerCopy:
        copy = self.s.exec(
            select(ReviewerCopy)
            .where(ReviewerCopy.review_id == review.id)
            .where(ReviewerCopy.user_id == user.id)
        ).first()
        if copy is None:
            copy = ReviewerCopy(review=review, user=user)
            self.s.add(copy)
        copy.content = content
        if based_on is not None:
            copy.based_on_version = based_on
        copy.submitted_at = submitted_at or _utcnow()
        self.s.flush()
        return copy

    def list(self, review: Review) -> list[ReviewerCopy]:
        return list(
            self.s.exec(
                select(ReviewerCopy)
                .where(ReviewerCopy.review_id == review.id)
                .order_by(ReviewerCopy.id)
            ).all()
        )


class RidRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def get(self, review: Review, rid_str: str) -> Optional[RID]:
        return self.s.exec(
            select(RID).where(RID.review_id == review.id).where(RID.rid_str == rid_str)
        ).first()

    def list(self, review: Review) -> list[RID]:
        return list(
            self.s.exec(select(RID).where(RID.review_id == review.id).order_by(RID.id)).all()
        )

    def add_change(
        self, rid: RID, version: DocumentVersion, *, note: Optional[str] = None
    ) -> RidChange:
        change = RidChange(rid=rid, version=version, note=note)
        self.s.add(change)
        self.s.flush()
        return change

    def changes_for(self, rid: RID) -> list[RidChange]:
        return list(
            self.s.exec(
                select(RidChange).where(RidChange.rid_id == rid.id).order_by(RidChange.id)
            ).all()
        )


class AuditRepo:
    def __init__(self, session: Session) -> None:
        self.s = session

    def log(
        self,
        *,
        action: str,
        target: str,
        actor: Optional[User] = None,
        detail: Optional[dict] = None,
    ) -> AuditLog:
        entry = AuditLog(actor=actor, action=action, target=target, detail_json=detail)
        self.s.add(entry)
        self.s.flush()
        return entry

    def list(self, *, action: Optional[str] = None) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        return list(self.s.exec(stmt).all())
