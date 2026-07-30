"""Finalize-time PDF export (v3 step 04). Optional: requires the ``malus[pdf]``
extra (markdown-it-py + WeasyPrint — ADR 0004). Import degrades gracefully:
without the extra ``PDF_AVAILABLE`` is False and callers skip PDF generation
with a visible notice instead of failing."""

from __future__ import annotations

import html

try:
    from markdown_it import MarkdownIt
    from weasyprint import HTML

    PDF_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via PDF_AVAILABLE tests
    PDF_AVAILABLE = False


class PdfUnavailable(RuntimeError):
    """The malus[pdf] extra is not installed."""


_CSS = """
@page { size: A4; margin: 2.2cm 1.8cm;
  @bottom-left { content: string(docid); font-size: 8pt; color: #666; }
  @bottom-right { content: counter(page) " / " counter(pages); font-size: 8pt; color: #666; } }
body { font-family: sans-serif; font-size: 10.5pt; line-height: 1.45; }
.malus-cover { page-break-after: always; string-set: docid attr(data-docid); }
.malus-cover h1 { font-size: 22pt; margin-top: 6cm; }
.malus-cover table { margin-top: 1cm; border-collapse: collapse; }
.malus-cover td { padding: .15cm .4cm; border-bottom: 1px solid #ddd; }
.malus-signature-page { page-break-before: always; }
.malus-signature-page table { width: 100%; border-collapse: collapse; font-size: 9pt; }
.malus-signature-page th, .malus-signature-page td { border: 1px solid #bbb; padding: .12cm .25cm; text-align: left; }
pre, code { font-family: monospace; font-size: 9pt; background: #f5f5f5; }
h1, h2, h3 { page-break-after: avoid; }
"""


def render_review_html(*, title, review_id, owner, content_md, verifications, sha_note) -> str:
    """The full print document: cover, rendered Markdown body, and a final
    sign-off page (document hash + per-finding verification table). Always
    generated as a whole so the archived PDF is self-contained."""
    if not PDF_AVAILABLE:
        raise PdfUnavailable("install malus[pdf] to export a PDF")
    # commonmark+table, not "gfm-like": the gfm preset renders links only with
    # the extra linkify-it-py dependency — tables are what the DUR needs
    body = MarkdownIt("commonmark").enable("table").render(content_md)
    esc = html.escape
    rows = "".join(
        f"<tr><td>{esc(v['rid'])}</td><td>{esc(v['disposition'] or '')}</td>"
        f"<td>{esc(v['status'])}</td><td>{esc(v['verified_by'] or '—')}</td>"
        f"<td>{esc(v['verified_on'] or '—')}</td></tr>"
        for v in verifications
    )
    return f"""<html><head><meta charset="utf-8"><style>{_CSS}</style></head><body>
<section class="malus-cover" data-docid="{esc(review_id)}">
  <h1>{esc(title or review_id)}</h1>
  <table>
    <tr><td>Review</td><td>{esc(review_id)}</td></tr>
    <tr><td>Owner</td><td>{esc(owner)}</td></tr>
    <tr><td>Status</td><td>finalized</td></tr>
  </table>
</section>
{body}
<section class="malus-signature-page">
  <h2>Review sign-off</h2>
  <p>{esc(sha_note)}</p>
  <table>
    <tr><th>RID</th><th>Disposition</th><th>Status</th><th>Verified by</th><th>On</th></tr>
    {rows}
  </table>
</section>
</body></html>"""


def generate_review_pdf(session, review) -> bytes:
    """Render the finalized review to PDF bytes (cover + document + sign-off).
    Called once at finalize; the result is archived as a ReviewArtifact."""
    if not PDF_AVAILABLE:
        raise PdfUnavailable("install malus[pdf] to export a PDF")
    import hashlib

    from malus.constants import Status
    from malus.repo import RidRepo, VersionRepo

    latest = VersionRepo(session).latest(review)
    content = latest.content if latest else ""
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    verifications = [
        {
            "rid": r.rid_str,
            "disposition": r.disposition,
            "status": r.status,
            "verified_by": r.verified_by.display_name if r.verified_by else None,
            "verified_on": r.verified_on.isoformat() if r.verified_on else None,
        }
        for r in RidRepo(session).list(review)
        if r.status != Status.WITHDRAWN.value
    ]
    markup = render_review_html(
        title=review.title,
        review_id=review.review_id_str,
        owner=review.owner.display_name,
        content_md=content,
        verifications=verifications,
        sha_note=f"Final document SHA-256: {sha}",
    )
    return HTML(string=markup).write_pdf()
