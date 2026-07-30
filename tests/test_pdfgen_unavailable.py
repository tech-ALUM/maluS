"""Without the malus[pdf] extra, pdfgen degrades with PdfUnavailable."""

from __future__ import annotations

import pytest

from malus import pdfgen


def test_unavailable_raises(monkeypatch):
    monkeypatch.setattr(pdfgen, "PDF_AVAILABLE", False)
    with pytest.raises(pdfgen.PdfUnavailable):
        pdfgen.render_review_html(
            title="t", review_id="r", owner="o", content_md="",
            verifications=[], sha_note="",
        )
    with pytest.raises(pdfgen.PdfUnavailable):
        pdfgen.generate_review_pdf(None, None)
