"""Import/export between the DB and the ``rtd.yaml`` interchange format.

`rtd.yaml` is no longer the store (ADR 0001) — it is an interchange format. This
module maps it losslessly onto the relational schema and back:

- names (``owner`` / ``reviewer`` / ``verified_by``) <-> :class:`User` rows
  (matched/created by ``display_name``);
- ``meta.baseline_sha`` <-> the baseline :class:`DocumentVersion.content_hash`;
- ``master`` (a rid id) <-> ``master_id`` FK; ``duplicates`` is **derived** from
  the inverse of that link, never stored;
- enum members <-> the ``.value`` strings held in the columns.

Enum values remain owned by ``malus.constants``; the RID/RTD dataclasses in
``malus.models`` remain the canonical in-memory representation.
"""

from __future__ import annotations

from sqlmodel import Session, select

from malus.constants import CommentType, Disposition, Kind, Role, Severity, Status
from malus.db.models import (
    Document,
    DocumentVersion,
    Review,
    ReviewMember,
    ReviewStatus,
    User,
)
from malus.db.models import RID as RidRow
from malus.models import RID, RTD, Anchor, Meta


def _enum_value(member) -> str | None:
    return None if member is None else member.value


def import_rtd(session: Session, rtd: RTD) -> Review:
    """Create the full review graph for ``rtd`` and return the :class:`Review`.

    Users are matched by ``display_name`` and created on demand (no auth in
    Step 1). Master links are resolved in a second pass so ordering does not
    matter.
    """
    cache: dict[str, User] = {}

    def user_for(name: str | None) -> User | None:
        if name is None:
            return None
        if name in cache:
            return cache[name]
        found = session.exec(select(User).where(User.display_name == name)).first()
        if found is None:
            found = User(username=name, display_name=name)
            session.add(found)
            session.flush()
        cache[name] = found
        return found

    meta = rtd.meta
    owner = user_for(meta.owner)
    review = Review(
        review_id_str=meta.review_id,
        rid_prefix=meta.rid_prefix,
        owner=owner,
        status=ReviewStatus.DRAFT.value,
        created=meta.created,
    )
    session.add(review)
    session.flush()

    document = Document(review=review, name=meta.document)
    session.add(document)
    session.flush()
    # The frozen baseline: its content is not carried by rtd.yaml, so we preserve
    # the original identity (git SHA for v0 imports) as the content hash.
    session.add(
        DocumentVersion(
            document=document,
            ordinal=1,
            content="",
            content_hash=meta.baseline_sha,
            is_baseline=True,
            created_by=owner,
        )
    )

    # Membership (order-preserving): owner then reviewers, as listed.
    session.add(ReviewMember(review=review, user=owner, role=Role.OWNER.value))
    for name in meta.reviewers:
        session.add(ReviewMember(review=review, user=user_for(name), role=Role.REVIEWER.value))
    session.flush()

    rows: dict[str, RidRow] = {}
    for r in rtd.rids:
        row = RidRow(
            review=review,
            rid_str=r.rid,
            reviewer=user_for(r.reviewer),
            created=r.created,
            anchor_json=r.anchor.to_dict(),
            kind=r.kind.value,
            type=_enum_value(r.type),
            severity=_enum_value(r.severity),
            status=r.status.value,
            comment=r.comment,
            reply=r.reply,
            disposition=_enum_value(r.disposition),
            resolution=r.resolution,
            verified_by=user_for(r.verified_by),
            verified_on=r.verified_on,
            ai_drafted=r.ai_drafted,
        )
        session.add(row)
        rows[r.rid] = row
    session.flush()

    for r in rtd.rids:  # second pass: resolve master links
        if r.master:
            rows[r.rid].master_id = rows[r.master].id
    session.flush()

    return review


def export_rtd(session: Session, review: Review) -> RTD:
    """Reconstruct the canonical :class:`RTD` for ``review`` from the DB."""
    document = review.documents[0]
    baseline = next((v for v in document.versions if v.is_baseline), None)

    members = sorted(review.members, key=lambda m: m.id)
    reviewers = [m.user.display_name for m in members if m.role == Role.REVIEWER.value]

    meta = Meta(
        review_id=review.review_id_str,
        document=document.name,
        baseline_sha=baseline.content_hash if baseline else "",
        created=review.created,
        owner=review.owner.display_name,
        reviewers=reviewers,
        rid_prefix=review.rid_prefix,
    )

    rids = []
    for row in sorted(review.rids, key=lambda r: r.id):
        rids.append(
            RID(
                rid=row.rid_str,
                reviewer=row.reviewer.display_name,
                created=row.created,
                anchor=Anchor.from_dict(row.anchor_json),
                kind=Kind(row.kind),
                type=None if row.type is None else CommentType(row.type),
                severity=None if row.severity is None else Severity(row.severity),
                status=Status(row.status),
                comment=row.comment,
                reply=row.reply,
                disposition=None if row.disposition is None else Disposition(row.disposition),
                resolution=row.resolution,
                master=row.master.rid_str if row.master else None,
                duplicates=[d.rid_str for d in sorted(row.duplicates, key=lambda d: d.id)],
                verified_by=row.verified_by.display_name if row.verified_by else None,
                verified_on=row.verified_on,
                ai_drafted=row.ai_drafted,
            )
        )
    return RTD(meta=meta, rids=rids)
