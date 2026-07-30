"""PDF pipeline (v3 step 04) — runs only with the malus[pdf] extra installed."""

from __future__ import annotations

import pytest

pytest.importorskip("weasyprint")
pytest.importorskip("markdown_it")

from sqlmodel import Session  # noqa: E402

from malus import services as svc  # noqa: E402
from malus.constants import Disposition  # noqa: E402
from malus.db import create_all, make_engine  # noqa: E402
from malus.pdfgen import generate_review_pdf, render_review_html  # noqa: E402


def _ctx():
    return dict(
        title="Sensor SRS",
        review_id="SIN-SRS-R1",
        owner="A. Boffi",
        content_md="# Doc\n\nBody with **bold** and a <tag>.\n",
        verifications=[
            {"rid": "SIN-SRS-0001", "disposition": "accepted", "status": "verified",
             "verified_by": "F. Miccoli", "verified_on": "2026-07-30"},
        ],
        sha_note="Final document SHA-256: abc123",
    )


def test_render_html_contains_cover_and_signature_page():
    markup = render_review_html(**_ctx())
    assert "malus-cover" in markup and "malus-signature-page" in markup
    assert "Final document SHA-256: abc123" in markup
    assert "SIN-SRS-0001" in markup and "F. Miccoli" in markup
    assert "&lt;tag&gt;" not in markup.split("malus-signature-page")[1]  # table text escaped upstream
    assert "<script" not in markup


def test_generate_pdf_bytes():
    engine = make_engine("sqlite://")
    create_all(engine)
    with Session(engine) as session:
        review = svc.create_review(
            session, review_id="PDF-R1", document_name="d.md",
            owner="own", reviewers=["rev"], title="PDF smoke",
        )
        svc.freeze_baseline(session, review, "# Doc\n\nThe quick fix.\n")
        svc.add_reviewer_copy(
            session, review, "rev",
            "# Doc\n\nThe quick fix.{COMM|type=technical|sev=major: bound it}\n",
        )
        svc.harvest(session, review)
        svc.answer(session, review, "PDF-0001", disposition=Disposition.ACCEPTED, reply="ok")
        svc.accept_disposition(session, review, "PDF-0001", reviewer="rev")
        svc.start_closeout(session, review)
        svc.save_closeout_version(session, review, "# Doc\n\nThe slow fix.\n", rid_ids=["PDF-0001"])
        svc.implement(session, review, "PDF-0001")
        svc.verify(session, review, "PDF-0001", reviewer="rev")
        session.commit()
        data = generate_review_pdf(session, review)
    assert data.startswith(b"%PDF")
    assert len(data) > 1000
