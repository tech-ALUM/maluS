# v3 Step 4 — Finalize, artifacts, MD + PDF export

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** surface finalize in the GUI and, once finalized, let members download
the final Markdown and an archived PDF (cover + document + signature page with
SHA-256 and the verification audit trail). PDF via the optional extra
`malus[pdf]`; graceful print-CSS fallback without it.

**Architecture:** new table `ReviewArtifact` stores the PDF bytes generated
once at finalize (prerequisite for step 05 signing). New module
`src/malus/pdfgen.py` isolates the optional imports (`markdown_it`,
`weasyprint`) behind `PDF_AVAILABLE`. Spec §Finalize, §Downloads, §PDF pipeline;
ADR 0004 records the first sanctioned optional runtime deps.

**Tech stack:** markdown-it-py + WeasyPrint (extra `pdf` only), Jinja, pytest
(`importorskip`). Depends on steps 01–03.

## Global constraints

- Core install stays dependency-clean: `malus` without extras must import,
  serve and finalize (PDF generation skipped with a visible notice).
- The PDF is generated **once** at finalize and stored; downloads serve the
  stored bytes (spec: signing needs a stable file).
- PDF tests: `pytest.importorskip("weasyprint")` at module level.
- Suite green + Conventional Commit per task.

## Deliverables

- [x] `ReviewArtifact` table + repo
- [x] `pdfgen.py`: MD→HTML→PDF with cover + signature page, `PDF_AVAILABLE` guard
- [x] Finalize service generates + stores the artifact; web Finalize button
- [x] Download routes: final MD, RTD report MD, PDF
- [x] Print-CSS fallback view
- [x] `pyproject.toml` extra `pdf` + ADR 0004
- [x] Full suite green

---

### Task 1: `ReviewArtifact` model + repo

**Files:**
- Modify: `src/malus/db/models.py` (after `RidChange`), `src/malus/repo/repositories.py`
- Test: `tests/db/test_artifacts.py` (new)

**Interfaces produced:**

```python
class ReviewArtifact(SQLModel, table=True):
    __tablename__ = "review_artifacts"
    id: Optional[int]
    review_id: int          # FK reviews.id
    kind: str               # "pdf" | "pdf_signed" (v3 vocabulary, plain string)
    content: bytes          # sa_column=Column(LargeBinary)
    sha256: str
    created: dt.datetime    # default _utcnow

class ArtifactRepo:         # repositories.py, same shape as the other repos
    def add(self, review, kind: str, content: bytes) -> ReviewArtifact   # computes sha256
    def get(self, review, kind: str) -> Optional[ReviewArtifact]         # latest by created
```

- [ ] **Step 1: failing test:** `ArtifactRepo(session).add(review, "pdf", b"%PDF-fake")`
  → `get(review, "pdf")` returns it with `sha256 == hashlib.sha256(b"%PDF-fake").hexdigest()`;
  `get(review, "pdf_signed")` is `None`.
- [ ] **Step 2:** run → FAIL. **Step 3:** implement model (use
  `Field(sa_column=Column(LargeBinary))` for `content`; import `LargeBinary`
  from sqlalchemy) + repo; export `ArtifactRepo` from `malus.repo`.
  `create_all` picks the table up — no migration script needed.
- [ ] **Step 4:** run → PASS. **Step 5:** `git commit -m "feat(db): ReviewArtifact stores finalize-time exports"`

### Task 2: PDF pipeline module

**Files:**
- Create: `src/malus/pdfgen.py`
- Modify: `pyproject.toml` (extra), `docs/adr/0004-optional-extras.md` (new)
- Test: `tests/test_pdfgen.py` (new)

**Interfaces produced:**

```python
PDF_AVAILABLE: bool
def render_review_html(*, title, review_id, owner, content_md, verifications, sha_note) -> str
def generate_review_pdf(session, review) -> bytes    # raises PdfUnavailable if not PDF_AVAILABLE
class PdfUnavailable(RuntimeError): ...
```

- [ ] **Step 1:** add to `pyproject.toml` `[project.optional-dependencies]`:

```toml
pdf = ["weasyprint>=62", "markdown-it-py>=3.0"]  # ADR 0004: finalize-time PDF export
```

  Write `docs/adr/0004-optional-extras.md`: context (v3 needs MD→PDF; core stays
  PyYAML+Typer+FastAPI-only per ADR 0002), decision (optional pip extras `pdf`
  — weasyprint + markdown-it-py — and `sign` — pyhanko, step 05; feature-detect
  at import, degrade with a visible notice, never at runtime download), status
  accepted, consequences (system Pango needed for weasyprint; documented in README).
- [ ] **Step 2: failing tests:**

```python
import pytest

weasyprint = pytest.importorskip("weasyprint")

from malus.pdfgen import generate_review_pdf, render_review_html


def test_render_html_contains_cover_and_signature_page(finalized_review_ctx):
    html = render_review_html(**finalized_review_ctx)
    assert "malus-cover" in html and "malus-signature-page" in html
    assert finalized_review_ctx["sha_note"] in html


def test_generate_pdf_bytes(session, finalized_review):
    data = generate_review_pdf(session, finalized_review)
    assert data.startswith(b"%PDF")
```

  And one test OUTSIDE the importorskip module (e.g. `tests/test_pdfgen_unavailable.py`)
  that monkeypatches `malus.pdfgen.PDF_AVAILABLE = False` and asserts
  `PdfUnavailable` is raised.
- [ ] **Step 3: implement** `src/malus/pdfgen.py`:

```python
"""Finalize-time PDF export (v3). Optional: requires the `malus[pdf]` extra
(markdown-it-py + WeasyPrint — ADR 0004). Import degrades gracefully."""

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
    if not PDF_AVAILABLE:
        raise PdfUnavailable("install malus[pdf] to export a PDF")
    body = MarkdownIt("gfm-like").render(content_md)
    rows = "".join(
        f"<tr><td>{html.escape(v['rid'])}</td><td>{html.escape(v['disposition'] or '')}</td>"
        f"<td>{html.escape(v['status'])}</td><td>{html.escape(v['verified_by'] or '—')}</td>"
        f"<td>{html.escape(v['verified_on'] or '—')}</td></tr>"
        for v in verifications
    )
    esc = html.escape
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
    if not PDF_AVAILABLE:
        raise PdfUnavailable("install malus[pdf] to export a PDF")
    import hashlib

    from malus.constants import Status
    from malus.repo import VersionRepo, RidRepo

    latest = VersionRepo(session).latest(review)
    content = latest.content if latest else ""
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    rows = RidRepo(session).list(review)
    verifications = [
        {
            "rid": r.rid_str,
            "disposition": r.disposition,
            "status": r.status,
            "verified_by": r.verified_by.display_name if r.verified_by else None,
            "verified_on": r.verified_on.isoformat() if r.verified_on else None,
        }
        for r in rows
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
```

  (If `MarkdownIt("gfm-like")` needs the linkify extra, fall back to
  `MarkdownIt("commonmark").enable("table")` — tables are the requirement;
  record whichever you ship under `## Deviations`.)
- [ ] **Step 4:** with the extra installed (`pip install -e .[pdf]` in the dev env)
  run `python -m pytest tests/test_pdfgen.py tests/test_pdfgen_unavailable.py -q` → PASS;
  full suite still green *without* the extra (importorskip).
- [ ] **Step 5:** `git commit -m "feat(pdf): finalize-time PDF pipeline behind malus[pdf] (ADR 0004)"`

### Task 3: finalize generates the artifact + web Finalize flow

**Files:**
- Modify: `src/malus/services/core.py` (`finalize` :615-642), `src/malus/web/router.py`,
  `src/malus/web/templates/review.html`
- Test: `tests/services/test_finalize_artifacts.py`, `tests/web/test_finalize_page.py` (new)

**Interfaces produced:** `svc.finalize(...)` additionally stores an
`ArtifactRepo` `"pdf"` artifact when `PDF_AVAILABLE` (never fails the finalize
if generation errors — logged + audited as `pdf_failed`);
`POST /ui/reviews/{id}/finalize`; dashboard Finalize button (owner, phase
closeout, gate satisfied) and post-finalize Downloads row.

- [ ] **Step 1: failing tests:** service — finalize on a satisfied gate flips phase
  to `finalized` and (with the pdf extra) stores an artifact whose bytes start
  `%PDF`; web — owner POST `/ui/reviews/{id}/finalize` with an unverified
  accepted RID → 409; with the gate satisfied → 303 and phase `finalized`;
  non-owner → 403.
- [ ] **Step 2:** run → FAIL. **Step 3: implement:**
  - in `finalize()` after `set_status(... FINALIZED ...)`:

```python
    from malus import pdfgen

    if pdfgen.PDF_AVAILABLE:
        try:
            pdf_bytes = pdfgen.generate_review_pdf(session, review)
            ArtifactRepo(session).add(review, "pdf", pdf_bytes)
            AuditRepo(session).log(action="export_pdf",
                                   target=f"review:{review.review_id_str}", actor=by)
        except Exception as exc:  # a broken PDF must not un-finalize the review
            AuditRepo(session).log(action="pdf_failed",
                                   target=f"review:{review.review_id_str}", actor=by,
                                   detail={"error": str(exc)})
```

  - web route `finalize_action`: owner+human (`authz.require_owner`,
    `authz.forbid_ai_commit`), call `svc.finalize(session, review, by=user)`;
    non-empty error list → 409 with the errors joined in `detail`; redirect to
    the dashboard.
  - `review.html`: in the phase-aware actions block (step 01), phase `closeout`:
    show `Finalize review` (with `onsubmit` confirm) when
    `finalize_ready` (router passes `svc.finalize`'s gate check — add a
    read-only `svc.finalize_gate(session, review) -> list[str]` sharing the
    blocking-RIDs logic with `finalize`, and use it here); phase `finalized`:
    show a Downloads row (Task 4 links) instead of workspace/actions.
- [ ] **Step 4:** run → PASS (suite-wide). **Step 5:** `git commit -m "feat(web): finalize flow — gate check, phase flip, stored PDF artifact"`

### Task 4: download routes + print fallback

**Files:**
- Modify: `src/malus/web/router.py`, `src/malus/web/templates/review.html`
- Create: `src/malus/web/templates/print.html`
- Test: `tests/web/test_downloads.py` (new)

**Interfaces produced:**
`GET /ui/reviews/{id}/download/final.md` · `GET /ui/reviews/{id}/download/report.md`
· `GET /ui/reviews/{id}/download/review.pdf` · `GET /ui/reviews/{id}/print`
(member/admin; all except `print` require phase `finalized` → else 409).

- [ ] **Step 1: failing tests:** finalized review — member GET `final.md` → 200,
  `text/markdown`, `Content-Disposition: attachment; filename="{review_id}-final.md"`,
  body = final version content; `report.md` → 200 with the `svc.report` render;
  `review.pdf` → 200 `application/pdf` when the artifact exists, **404 with a
  clear detail** (*"PDF was not generated — install malus[pdf] and re-finalize"*)
  when it does not; non-member → 403; phase closeout → 409; `print` → 200 HTML
  containing the rendered document and a `window.print()` button.
- [ ] **Step 2:** run → FAIL. **Step 3: implement** — small routes, one pattern:

```python
@web.get("/ui/reviews/{review_id}/download/final.md")
def download_final_md(review_id: str, request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if authz.review_role(session, review, user) is None and not user.is_admin:
        raise HTTPException(status_code=403, detail="members only")
    if review.status != ReviewStatus.FINALIZED.value:
        raise HTTPException(status_code=409, detail="the review is not finalized yet")
    latest = VersionRepo(session).latest(review)
    return Response(
        content=latest.content if latest else "",
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{review_id}-final.md"'},
    )
```

  `report.md` uses `svc.report(session, review)` (second tuple element);
  `review.pdf` serves `ArtifactRepo(session).get(review, "pdf").content` as
  `application/pdf` with attachment disposition. `print.html`: `base.html`
  extension rendering the final MD through the vendored `marked` (like the
  viewer) plus a `@media print` stylesheet block hiding nav/buttons; a
  "Print / Save as PDF" button calling `window.print()` — the zero-dependency
  fallback (spec §PDF pipeline). Downloads row in `review.html` links the four
  routes; the PDF link is present only when the artifact exists (router passes
  `has_pdf`), otherwise show the fallback hint linking `/print`.
- [ ] **Step 4:** run → PASS. **Step 5:** `git commit -m "feat(web): finalized downloads — final MD, RTD report, archived PDF, print fallback"`

## Deviations

- markdown-it preset is `commonmark`+`table`, not `gfm-like` (the gfm preset
  needs the extra linkify-it-py dependency at render time; tables are the
  requirement).
- An Alembic revision (`b9e4d5f6a701`) ships `review_artifacts` AND the
  step-wave `reviewer_copies.reopen_requested_at` column — the repo's schema
  test pins migrations == models, which create_all-only changes would break.
- The print fallback (`/print`) is available to members in any post-freeze
  phase, not only finalized (it doubles as a quick print of the current
  document state).
- Report download asserts on the minutes title (RID ids are not guaranteed
  verbatim in the report body).

## Definition of Done

- [x] Deliverables checked; `python -m pytest -q` green (importorskip covers
  the without-extra path; unavailable-degradation pinned by
  tests/test_pdfgen_unavailable.py).
- [x] Manual smoke (with extra, browser): finalize button appears only with
  the gate satisfied → phase flips to finalized → Downloads row serves
  final.md / report.md / PDF; archived artifact is %PDF-1.7, 12.6 KB, with
  cover + sign-off page (structure pinned by tests/test_pdfgen.py).
- [x] README gains an *Install extras* subsection (`pip install malus[pdf]`,
  system Pango note).

## Out of scope

Digital signature (05); release chores (06).
