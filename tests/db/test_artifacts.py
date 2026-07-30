"""ReviewArtifact (v3 step 04): finalize-time exports stored once, served verbatim."""

from __future__ import annotations

import hashlib

from sqlmodel import Session

from malus import services as svc
from malus.repo import ArtifactRepo


def _review(session: Session):
    return svc.create_review(
        session, review_id="ART-R1", document_name="d.md", owner="own"
    )


def test_add_and_get_artifact(session: Session):
    review = _review(session)
    ArtifactRepo(session).add(review, "pdf", b"%PDF-fake")
    session.commit()
    art = ArtifactRepo(session).get(review, "pdf")
    assert art is not None and art.content == b"%PDF-fake"
    assert art.sha256 == hashlib.sha256(b"%PDF-fake").hexdigest()
    assert ArtifactRepo(session).get(review, "pdf_signed") is None


def test_get_returns_latest_of_kind(session: Session):
    review = _review(session)
    ArtifactRepo(session).add(review, "pdf", b"%PDF-1")
    ArtifactRepo(session).add(review, "pdf", b"%PDF-2")
    session.commit()
    assert ArtifactRepo(session).get(review, "pdf").content == b"%PDF-2"
