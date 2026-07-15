"""v1.6 API parity: ``PUT /copies/{user}`` saves a draft (``submitted_at`` NULL);
``POST /copies/{user}/submit`` marks the copy submitted."""

from __future__ import annotations

from sqlmodel import Session, select

from malus.db.models import ReviewerCopy

R = "SIN-SRS-R1"


def _seed(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    return owner, f


def _only_copy(app):
    with Session(app.state.engine) as s:
        return s.exec(select(ReviewerCopy)).one()


def test_put_copy_saves_a_draft(app, mkuser, docs):
    _owner, f = _seed(mkuser, docs)
    assert (
        f.put(f"/reviews/{R}/copies/F. Miccoli", json={"content": docs["copy_f"]}).status_code
        == 200
    )
    assert _only_copy(app).submitted_at is None  # draft, not submitted


def test_submit_copy_marks_submitted(app, mkuser, docs):
    _owner, f = _seed(mkuser, docs)
    assert (
        f.post(
            f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]}
        ).status_code
        == 200
    )
    assert _only_copy(app).submitted_at is not None  # submitted
