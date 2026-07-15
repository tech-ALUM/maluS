"""Server-side authorization: review-scoped roles + the closure invariant.

The permission matrix (v1 Step 4):

- **owner** — edit the DUR, freeze, answer/implement RIDs, create changes,
  finalize. Never verify/reopen.
- **reviewer** — edit only their own copy; verify/reopen only their own RIDs.
- **moderator** — harvest/triage; verify/reopen on a reviewer's behalf.
- **admin** — user management only (no power over review content).
- **AI principals** (``is_ai``) — never verify/reopen, regardless of role.

These checks run *in front of* the services, which still enforce the closure
invariant themselves (defense-in-depth).
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from malus.constants import Role
from malus.db.models import RID, Review, ReviewMember, User


def review_role(session: Session, review: Review, user: User) -> Optional[str]:
    member = session.exec(
        select(ReviewMember)
        .where(ReviewMember.review_id == review.id)
        .where(ReviewMember.user_id == user.id)
    ).first()
    return member.role if member else None


def _forbid(message: str) -> None:
    raise HTTPException(status_code=403, detail=message)


def require_owner(session: Session, review: Review, user: User) -> None:
    if review_role(session, review, user) != Role.OWNER.value:
        _forbid("owner role required for this action")


def forbid_ai_commit(user: User) -> None:
    """An AI principal may DRAFT but never COMMIT an owner decision (v1.7):
    answer/implement/finalize. Drafting (``update_rid``, no transition) stays
    allowed. The services enforce the same rule (defense-in-depth)."""
    if user.is_ai:
        _forbid("AI principals may only draft a disposition; a human owner must confirm it")


def require_moderator(session: Session, review: Review, user: User) -> None:
    if review_role(session, review, user) != Role.MODERATOR.value:
        _forbid("moderator role required (harvest/triage)")


def require_owner_or_moderator(session: Session, review: Review, user: User) -> None:
    if review_role(session, review, user) not in (Role.OWNER.value, Role.MODERATOR.value):
        _forbid("owner or moderator role required")


def require_own_copy(session: Session, review: Review, user: User, target: str) -> None:
    role = review_role(session, review, user)
    if role != Role.REVIEWER.value or target != user.display_name:
        _forbid("a reviewer may only edit their own copy")


def require_verify(session: Session, review: Review, user: User, rid: RID) -> bool:
    """Authorize verify/reopen; returns True if acting as moderator (on behalf)."""
    if user.is_ai:
        _forbid("AI principals may never verify or reopen a RID")
    role = review_role(session, review, user)
    if role == Role.MODERATOR.value:
        return True
    if role == Role.REVIEWER.value and rid.reviewer_id == user.id:
        return False
    _forbid("only the RID's own reviewer, or a moderator, may verify or reopen it")
    return False  # unreachable
