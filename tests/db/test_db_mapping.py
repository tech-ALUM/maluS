"""Lossless ``rtd.yaml`` <-> DB mapping (Step-1 Definition of Done).

Proves that a review can be imported into the DB and produced back as an
identical ``rtd.yaml`` — for every RID field, including the master/duplicate
clustering, verification stamps, SUGG null type/severity, ai_drafted, and
null anchor members.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from sqlmodel import Session, select

from malus.constants import CommentType, Disposition, Kind, Severity, Status
from malus.db import User, create_all, make_engine
from malus.db.models import RID as RidRow
from malus.db.rtd_io import export_rtd, import_rtd
from malus.models import RID, RTD, Anchor, Meta

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _rich_rtd() -> RTD:
    """A review exercising every RID field and both clustering directions."""
    meta = Meta(
        review_id="SIN-SRS-R1",
        document="reviews/SIN-SRS-R1/baseline.md",
        baseline_sha="9f1c2ab",
        created=dt.date(2026, 7, 3),
        owner="A. Boffi",
        reviewers=["F. Miccoli", "R. Bianchi", "G. Verdi"],
        rid_prefix="SIN-SRS",
    )
    rids = [
        # master COMM, accepted + verified
        RID(
            rid="SIN-SRS-0001",
            reviewer="F. Miccoli",
            created=dt.date(2026, 7, 3),
            anchor=Anchor(section="3.2.1", quote="…the timeout…", line_hint=142),
            kind=Kind.COMM,
            type=CommentType.TECHNICAL,
            severity=Severity.MAJOR,
            status=Status.VERIFIED,
            comment="The timeout must be bounded.",
            reply="Agreed; added an upper bound.",
            disposition=Disposition.ACCEPTED,
            resolution="Set max 30s in §3.2.1.",
            duplicates=["SIN-SRS-0002"],
            verified_by="F. Miccoli",
            verified_on=dt.date(2026, 7, 9),
        ),
        # duplicate of 0001, still open, partial anchor
        RID(
            rid="SIN-SRS-0002",
            reviewer="R. Bianchi",
            created=dt.date(2026, 7, 3),
            anchor=Anchor(section="3.2.1", quote=None, line_hint=None),
            kind=Kind.COMM,
            type=CommentType.TECHNICAL,
            severity=Severity.MINOR,
            status=Status.OPEN,
            comment="Is the timeout unbounded?",
            master="SIN-SRS-0001",
        ),
        # SUGG (null type/severity), answered, ai-drafted, empty anchor
        RID(
            rid="SIN-SRS-0003",
            reviewer="G. Verdi",
            created=dt.date(2026, 7, 4),
            anchor=Anchor(),
            kind=Kind.SUGG,
            status=Status.ANSWERED,
            comment='"teh" -> "the"',
            reply="Applied.",
            disposition=Disposition.ACCEPTED,
            ai_drafted=True,
        ),
        # rejected COMM, verified straight from answered
        RID(
            rid="SIN-SRS-0004",
            reviewer="F. Miccoli",
            created=dt.date(2026, 7, 5),
            anchor=Anchor(section="5", quote="scope", line_hint=200),
            kind=Kind.COMM,
            type=CommentType.PROCESS,
            severity=Severity.CRITICAL,
            status=Status.VERIFIED,
            comment="This looks out of scope.",
            reply="Rejected — it is in scope per the SOW.",
            disposition=Disposition.REJECTED,
            resolution="No change.",
            verified_by="F. Miccoli",
            verified_on=dt.date(2026, 7, 9),
        ),
        # withdrawn COMM (typo/minor)
        RID(
            rid="SIN-SRS-0005",
            reviewer="R. Bianchi",
            created=dt.date(2026, 7, 6),
            anchor=Anchor(section=None, quote="typo maybe", line_hint=None),
            kind=Kind.COMM,
            type=CommentType.TYPO,
            severity=Severity.MINOR,
            status=Status.WITHDRAWN,
            comment="never mind",
        ),
        # accepted COMM, implemented (editorial/major)
        RID(
            rid="SIN-SRS-0006",
            reviewer="G. Verdi",
            created=dt.date(2026, 7, 7),
            anchor=Anchor(section="4.1", quote="shall", line_hint=88),
            kind=Kind.COMM,
            type=CommentType.EDITORIAL,
            severity=Severity.MAJOR,
            status=Status.IMPLEMENTED,
            comment="Reword for clarity.",
            reply="Done.",
            disposition=Disposition.ACCEPTED,
            resolution="Reworded §4.1.",
        ),
    ]
    return RTD(meta=meta, rids=rids)


def test_rich_rtd_db_roundtrip_is_byte_identical(session: Session):
    text = _rich_rtd().to_yaml()
    review = import_rtd(session, RTD.from_yaml(text))
    session.commit()

    exported = export_rtd(session, review)
    assert exported.to_yaml() == text


def test_roundtrip_preserves_rid_field_details(session: Session):
    review = import_rtd(session, _rich_rtd())
    session.commit()
    exported = export_rtd(session, review)
    by_id = {r.rid: r for r in exported.rids}

    # order preserved (document order)
    assert [r.rid for r in exported.rids] == [
        "SIN-SRS-0001",
        "SIN-SRS-0002",
        "SIN-SRS-0003",
        "SIN-SRS-0004",
        "SIN-SRS-0005",
        "SIN-SRS-0006",
    ]
    # clustering survives both ways (duplicates derived from master link)
    assert by_id["SIN-SRS-0001"].duplicates == ["SIN-SRS-0002"]
    assert by_id["SIN-SRS-0002"].master == "SIN-SRS-0001"
    # names round-trip via User.display_name
    assert by_id["SIN-SRS-0001"].verified_by == "F. Miccoli"
    assert by_id["SIN-SRS-0001"].reviewer == "F. Miccoli"
    # SUGG has null type/severity, ai_drafted preserved
    assert by_id["SIN-SRS-0003"].kind is Kind.SUGG
    assert by_id["SIN-SRS-0003"].type is None
    assert by_id["SIN-SRS-0003"].severity is None
    assert by_id["SIN-SRS-0003"].ai_drafted is True
    # anchor null members survive
    assert by_id["SIN-SRS-0002"].anchor.quote is None
    assert by_id["SIN-SRS-0002"].anchor.section == "3.2.1"


def test_enum_columns_stored_as_values(session: Session):
    """The RID rows hold the enum .value strings, not enum objects."""
    import_rtd(session, _rich_rtd())
    session.commit()
    row = session.exec(select(RidRow).where(RidRow.rid_str == "SIN-SRS-0001")).one()
    assert row.kind == "COMM"
    assert row.type == "technical"
    assert row.severity == "major"
    assert row.status == "verified"
    assert row.disposition == "accepted"


def test_import_is_idempotent_across_databases(session: Session):
    """DB1 -> rtd.yaml -> DB2 -> rtd.yaml is stable (produced-from-DB re-imports identically)."""
    review1 = import_rtd(session, _rich_rtd())
    session.commit()
    first = export_rtd(session, review1)

    engine2 = make_engine("sqlite://")
    create_all(engine2)
    with Session(engine2) as s2:
        review2 = import_rtd(s2, first)
        s2.commit()
        second = export_rtd(s2, review2)

    assert second.to_yaml() == first.to_yaml()


def test_placeholder_users_created_and_deduplicated(session: Session):
    """Import creates one User per distinct rtd name (owner + 3 reviewers = 4)."""
    import_rtd(session, _rich_rtd())
    session.commit()
    names = {u.display_name for u in session.exec(select(User)).all()}
    assert names == {"A. Boffi", "F. Miccoli", "R. Bianchi", "G. Verdi"}


def test_sample_fixture_meta_roundtrips(session: Session):
    """The real (rids: []) sample fixture round-trips, incl. reviewer order and
    an absent rid_prefix (derived, not stored)."""
    text = (FIXTURES / "sample-review" / "rtd.yaml").read_text()
    original = RTD.from_yaml(text)
    review = import_rtd(session, original)
    session.commit()
    exported = export_rtd(session, review)
    assert exported.to_yaml() == original.to_yaml()
    assert exported.meta.reviewers == ["F. Miccoli", "R. Bianchi", "G. Verdi"]
    assert exported.meta.rid_prefix is None
