# v3.1 Step 4 — Downloads: baseline, self-contained diff, entry points

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** a terminated review hands back everything a member needs, from both
places a member actually stands. Two new member-only, finalized-only routes —
`download/baseline.md` (the frozen original) and `download/diff.html` (a
self-contained, printable baseline→final diff) — complete the set to
**`baseline.md · final.md · diff.html · report.md · PDF`**, and that set is
reachable from the review dashboard *and* from a `⋯` menu on every finalized
row of `/ui/reviews`.

**Architecture:** the two routes reuse the existing `_member_finalized` gate
(`router.py:1097`) verbatim — one authz rule for all five downloads. The diff
file is rendered from a **new standalone Jinja template**
`src/malus/web/templates/diff_download.html` that deliberately does **not**
extend `base.html`: it is a file the user keeps, not an app page, so it carries
its own `<!doctype>`, its own inline `<style>` and zero references to
`/static/*`. The reviews list grows a per-row `has_pdf` flag fed by **one**
batched artifact query (`ArtifactRepo.review_ids_with`), never one query per
row. Design: `docs/plan/v3.1/00-design.md`, rows *Downloads* and *Downloads
entry points*.

**Tech stack:** FastAPI `Response`, Jinja, stdlib `difflib` via
`malus.diffing`, SQLModel `select(...).distinct()`, pytest + SQLAlchemy's
`before_cursor_execute` event for the query-count assertion.

**DEPENDENCY — v3.1 step 03.** This step calls
`html_diff(old, new, *, context: int | None = 3, line_numbers: bool = False)`
with `context=None` ("whole document", `get_opcodes()` instead of
`get_grouped_opcodes()`) and `line_numbers=True` (two gutter `<span>`s per row,
old and new). That signature is **delivered by
`docs/plan/v3.1/03-diff-views.md`**; today `src/malus/diffing.py:41` still
reads `def html_diff(old, new, *, context: int = 3)`. Do not start Task 2
before step 03 is merged, and before writing Task 2's CSS **read the shipped
`src/malus/diffing.py`** to copy the exact gutter class name it emits.
Tasks 1, 3 and 4 have no such dependency.

## Global constraints

- Python 3.12+; **no new runtime dependencies** — the diff HTML is stdlib
  `difflib` through `malus.diffing` (ADR 0002 unchanged).
- **No new vendored JS** (ADR 0003). `diff_download.html` contains no
  `<script>` at all: it must render correctly from a `file://` double-click,
  offline, in any browser.
- The PDF stays the optional extra `malus[pdf]` (ADR 0004). Its absence must
  never break a page: the fifth slot degrades to the existing `Print view`
  link, exactly as `review.html:104-108` already does.
- All diff text is **escaped server-side** by `malus.diffing.html_diff` before
  any markup is added; the template inserts it with `| safe` and adds nothing
  unescaped of its own (review id and title go through normal autoescaping —
  Starlette's `select_autoescape()` covers `.html` templates).
- Never turn the reviews list into an N+1: `reviews_page` loops over *every*
  review, so any per-row datum must come from a batched lookup.
- Conventional Commits; `python -m pytest -q` green at the end of every task.

## Deliverables

- [x] `GET /ui/reviews/{review_id}/download/baseline.md` — frozen original,
  `text/markdown; charset=utf-8`, attachment `{review_id}-baseline.md`
- [x] `src/malus/web/templates/diff_download.html` — standalone, inline CSS,
  no JS, no `base.html`
- [x] `GET /ui/reviews/{review_id}/download/diff.html` —
  `text/html; charset=utf-8`, attachment `{review_id}-diff.html`
- [x] Dashboard downloads row extended to `baseline.md · final.md · diff.html
  · report.md · PDF` (PDF slot keeps its `has_pdf` / `Print view` fallback)
- [x] `ArtifactRepo.review_ids_with(kind)` — one query for a whole list page
- [x] `reviews_page` rows carry `status` + `has_pdf`; `reviews.html` shows a
  `⋯` menu with the five links on finalized rows (members / global admin)
- [x] README download sentence updated to the five-artifact set
- [x] Full suite green

---

### Task 1: `download/baseline.md`

**Files:**
- Modify: `src/malus/web/router.py` (insert immediately **before**
  `download_final_md`, `router.py:1109` — the route order mirrors the reading
  order of the artifacts)
- Test: `tests/web/test_finalize_downloads.py` (extend; it already owns the
  `_to_closeout` seed helper and the `R` / `FINAL_MD` constants)

**Interfaces produced:**
`GET /ui/reviews/{review_id}/download/baseline.md` → `200 text/markdown`,
`Content-Disposition: attachment; filename="{review_id}-baseline.md"`;
`409` unless phase `finalized`; `403` for a non-member (all three from the
existing `_member_finalized`).

- [x] **Step 1: failing tests** — append to
  `tests/web/test_finalize_downloads.py`:

```python
def test_baseline_download_serves_the_frozen_original(mkuser, docs):
    owner, f = _to_closeout(mkuser, docs)
    assert owner.post(f"/ui/reviews/{R}/finalize", follow_redirects=False).status_code == 303

    for client in (owner, f):  # any member, owner and reviewer alike
        r = client.get(f"/ui/reviews/{R}/download/baseline.md")
        assert r.status_code == 200
        assert r.text == docs["baseline"]  # the frozen original…
        assert r.text != FINAL_MD          # …not the final text
        assert r.headers["content-type"].startswith("text/markdown")
        assert r.headers["content-disposition"] == f'attachment; filename="{R}-baseline.md"'


def test_baseline_download_gate(mkuser, docs):
    owner, _f = _to_closeout(mkuser, docs)
    # still in closeout: nothing is downloadable yet
    assert owner.get(f"/ui/reviews/{R}/download/baseline.md").status_code == 409
    owner.post(f"/ui/reviews/{R}/finalize")
    outsider = mkuser("nobody", "No Body")
    assert outsider.get(f"/ui/reviews/{R}/download/baseline.md").status_code == 403
```

- [x] **Step 2: run** `python -m pytest tests/web/test_finalize_downloads.py -q`
  → **FAIL** (404: the route does not exist).
- [x] **Step 3: implement** in `src/malus/web/router.py`:

```python
@web.get("/ui/reviews/{review_id}/download/baseline.md")
def download_baseline_md(review_id: str, request: Request, session: Session = Depends(get_session)):
    """The frozen original (v3.1 step 04) — what the reviewers actually read,
    kept next to the final text so the pair is auditable outside maluS."""
    _user, review, redirect = _member_finalized(session, request, review_id)
    if redirect is not None:
        return redirect
    baseline = VersionRepo(session).baseline(review)
    return Response(
        content=baseline.content if baseline else "",
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{review_id}-baseline.md"'},
    )
```

  `VersionRepo` and `Response` are already imported (`router.py:19,36`); no new
  imports.
- [x] **Step 4: run** `python -m pytest tests/web/test_finalize_downloads.py -q`
  → **PASS**, then `python -m pytest -q` → green.
- [x] **Step 5: commit**
  `git commit -m "feat(web): download the frozen baseline of a finalized review"`

### Task 2: self-contained `download/diff.html`

**DEPENDS ON v3.1 step 03** — `html_diff(..., context=None, line_numbers=True)`.
Verify it exists (`grep -n "def html_diff" src/malus/diffing.py`) before
starting, and read the gutter markup it emits so the inline CSS below targets
the real class names.

**Files:**
- Create: `src/malus/web/templates/diff_download.html`
- Modify: `src/malus/web/router.py` (after `download_final_md`)
- Test: `tests/web/test_finalize_downloads.py` (extend)

**Interfaces produced:**
`GET /ui/reviews/{review_id}/download/diff.html` → `200 text/html; charset=utf-8`,
`Content-Disposition: attachment; filename="{review_id}-diff.html"`; same
`_member_finalized` gate; body = one HTML file with an inline `<style>`, a
header carrying review id, title and the baseline→latest ordinals, and the
whole-document line-numbered diff.

- [x] **Step 1: failing tests** — append to
  `tests/web/test_finalize_downloads.py`. Note the second test needs a change
  far from the top of the document, so make `_to_closeout` accept the closeout
  content: change its signature to
  `def _to_closeout(mkuser, docs, final_md: str = FINAL_MD):` and use
  `final_md` in the `POST /ui/reviews/{R}/closeout` body — every existing call
  site keeps working unchanged.

```python
def test_diff_download_is_a_self_contained_html_file(mkuser, docs):
    owner, f = _to_closeout(mkuser, docs)
    owner.post(f"/ui/reviews/{R}/finalize")

    for client in (owner, f):
        r = client.get(f"/ui/reviews/{R}/download/diff.html")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert r.headers["content-disposition"] == f'attachment; filename="{R}-diff.html"'
        body = r.text
        assert body.lstrip().lower().startswith("<!doctype html>")
        assert R in body                      # header: review id…
        assert "v1" in body and "v2" in body   # …and the version ordinals
        assert "<style>" in body               # CSS is inline…
        assert "<script" not in body           # …there is no JS…
        assert "/static/" not in body          # …and nothing is loaded from the app
        assert "<ins>" in body and "<del>" in body


def test_diff_download_is_the_whole_document_with_line_numbers(mkuser, docs):
    # a change in the LAST line: with the compact ±3-line view the title 8
    # lines above would be elided, so its presence pins context=None
    tail_edit = docs["baseline"].replace(
        "All measurements are written to disk in CSV format.",
        "All measurements are written to disk in CSV format, one file per run.",
    )
    owner, _f = _to_closeout(mkuser, docs, final_md=tail_edit)
    owner.post(f"/ui/reviews/{R}/finalize")

    body = owner.get(f"/ui/reviews/{R}/download/diff.html").text
    assert "# Sensor Interface Requirements" in body     # whole document
    assert "diff-ln" in body                             # line-number gutters


def test_diff_download_gate(mkuser, docs):
    owner, _f = _to_closeout(mkuser, docs)
    assert owner.get(f"/ui/reviews/{R}/download/diff.html").status_code == 409
    owner.post(f"/ui/reviews/{R}/finalize")
    outsider = mkuser("nobody", "No Body")
    assert outsider.get(f"/ui/reviews/{R}/download/diff.html").status_code == 403
```

- [x] **Step 2: run** `python -m pytest tests/web/test_finalize_downloads.py -q`
  → **FAIL** (404).
- [x] **Step 3a: create** `src/malus/web/templates/diff_download.html` — a
  whole document, **not** `{% extends "base.html" %}`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ review.review_id_str }} — diff v{{ baseline.ordinal }} → v{{ latest.ordinal }}</title>
<style>
  /* Standalone export (v3.1 step 04): every rule is inline and every colour is
     literal — this file is opened from disk, with no access to app.css. */
  body { margin: 0; padding: 2rem 1.5rem; background: #fff; color: #15181D;
         font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  .hd { border-bottom: 1px solid #dfe4ea; padding-bottom: .8rem; margin-bottom: 1.2rem; }
  .hd h1 { font-size: 1.2rem; margin: 0 0 .25rem; }
  .hd .sub { margin: 0; font-size: .85rem; color: #6b7580; }
  .hd .legend { margin: .55rem 0 0; font-size: .78rem; }
  .hd .legend span { padding: .05rem .4rem; border-radius: 3px; margin-right: .4rem; }
  .hd .legend .k-del { background: #fbe3e6; color: #a3142b; }
  .hd .legend .k-ins { background: #e2f2e8; color: #1d6b45; }
  .none { color: #6b7580; }
  .diff { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
          font-size: 13px; white-space: pre-wrap; overflow-x: auto; }
  .diff-ctx { opacity: .65; }
  .diff-del { background: #fbe3e6; }
  .diff-ins { background: #e2f2e8; }
  .diff del { color: #a3142b; text-decoration: line-through; }
  .diff ins { color: #1d6b45; text-decoration: none; font-weight: 600; }
  .diff-skip { text-align: center; opacity: .5; }
  .diff-ln { display: inline-block; width: 3.2em; text-align: right; padding-right: .6em;
             color: #9aa4ae; -webkit-user-select: none; user-select: none; }
  @media print { body { padding: 0; } .diff { font-size: 11px; } }
</style>
</head>
<body>
<header class="hd">
  <h1>{{ review.review_id_str }}{% if review.title %} — {{ review.title }}{% endif %}</h1>
  <p class="sub">Baseline v{{ baseline.ordinal }} → final v{{ latest.ordinal }} · exported from maluS</p>
  <p class="legend"><span class="k-del">removed</span><span class="k-ins">added</span></p>
</header>
{% if diff_html %}
{{ diff_html | safe }}
{% else %}
<p class="none">No changes — the final document is identical to the frozen baseline.</p>
{% endif %}
</body>
</html>
```

  If step 03's gutter spans use a class other than `diff-ln`, rename the rule
  (and the test assertion) to match and record it under `## Deviations`.
- [x] **Step 3b: implement** the route in `src/malus/web/router.py`, after
  `download_final_md`:

```python
@web.get("/ui/reviews/{review_id}/download/diff.html")
def download_diff_html(review_id: str, request: Request, session: Session = Depends(get_session)):
    """Self-contained baseline→final diff (v3.1 step 04): one HTML file, inline
    CSS, no scripts and no /static references, so it survives being e-mailed or
    archived beside the PDF. `html_diff` escapes every line before adding
    markup (v3.1 step 03 supplies context=None / line_numbers)."""
    _user, review, redirect = _member_finalized(session, request, review_id)
    if redirect is not None:
        return redirect
    versions = VersionRepo(session)
    baseline, latest = versions.baseline(review), versions.latest(review)
    if baseline is None or latest is None:  # defensive: a finalized review always has both
        raise HTTPException(status_code=409, detail="the baseline is not frozen yet")
    markup = templates.get_template("diff_download.html").render(
        review=review,
        baseline=baseline,
        latest=latest,
        diff_html=html_diff(baseline.content, latest.content, context=None, line_numbers=True),
    )
    return Response(
        content=markup,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{review_id}-diff.html"'},
    )
```

  `templates.get_template(...).render(...)` rather than `TemplateResponse`: the
  file is an artifact, not a page — it takes no `request` context and must not
  inherit the app chrome. Autoescaping still applies (`select_autoescape()`
  covers `.html`).
- [x] **Step 4: run** `python -m pytest tests/web/test_finalize_downloads.py -q`
  → **PASS**, then `python -m pytest -q` → green.
- [x] **Step 5: commit**
  `git commit -m "feat(web): self-contained baseline-to-final diff download"`

### Task 3: the dashboard downloads row, complete

**Files:**
- Modify: `src/malus/web/templates/review.html` (the finalized block,
  lines 99-109), `README.md` (line ~30)
- Test: `tests/web/test_finalize_downloads.py` (extend)

**Interfaces produced:** on a finalized review the dashboard renders
`baseline.md · final.md · diff.html · report.md · PDF`, in that order; the last
entry stays conditional on `has_pdf` (already computed at `router.py:339`).

- [x] **Step 1: failing test** — append to
  `tests/web/test_finalize_downloads.py`:

```python
def test_dashboard_shows_the_full_download_set_in_order(mkuser, docs):
    owner, _f = _to_closeout(mkuser, docs)
    owner.post(f"/ui/reviews/{R}/finalize")
    page = owner.get(f"/ui/reviews/{R}").text

    names = ("baseline.md", "final.md", "diff.html", "report.md")
    positions = [page.index(f"/ui/reviews/{R}/download/{n}") for n in names]
    assert positions == sorted(positions), "links must read baseline → final → diff → report"

    from malus import pdfgen

    if pdfgen.PDF_AVAILABLE:  # the archived PDF closes the row…
        assert f"/ui/reviews/{R}/download/review.pdf" in page
    else:                     # …or the zero-dependency print fallback does
        assert f"/ui/reviews/{R}/print" in page
```

  (`str.index` raises `ValueError` if a link is missing, so the list
  comprehension is itself the presence assertion.)
- [x] **Step 2: run** `python -m pytest tests/web/test_finalize_downloads.py -q`
  → **FAIL** (`ValueError: substring not found` on `baseline.md`).
- [x] **Step 3: implement** — replace `review.html:100-103` with the full set,
  leaving the `{% if has_pdf %}` branch at `104-108` untouched:

```html
  {# v3.1 step 04: the review is done — every member downloads the whole set:
     the frozen original, the final text, the diff between them, the minutes,
     and the archived PDF (or the print fallback when malus[pdf] was absent). #}
  <span class="muted">Downloads:</span>
  <a class="btn secondary" href="/ui/reviews/{{ review.review_id_str }}/download/baseline.md"
     title="The frozen original, exactly as the reviewers read it">baseline.md</a>
  <a class="btn secondary" href="/ui/reviews/{{ review.review_id_str }}/download/final.md">final.md</a>
  <a class="btn secondary" href="/ui/reviews/{{ review.review_id_str }}/download/diff.html"
     title="Self-contained baseline → final diff, with line numbers">diff.html</a>
  <a class="btn secondary" href="/ui/reviews/{{ review.review_id_str }}/download/report.md">report.md</a>
```

  Then update `README.md` step 8 so the documented set matches the shipped one:

```md
8. **Finalize** produces the finalized document plus review minutes —
   downloadable as `baseline.md`, `final.md`, a self-contained `diff.html`,
   the RTD report, and an archived PDF (`malus[pdf]`).
```

  and, in *Optional extras*, extend the fallback sentence to
  "…downloads offer the baseline, the final Markdown, the diff and the RTD
  report, and a zero-dependency browser print view replaces the PDF."
- [x] **Step 4: run** `python -m pytest tests/web/test_finalize_downloads.py -q`
  → **PASS**, then `python -m pytest -q` → green.
- [x] **Step 5: commit**
  `git commit -m "feat(web): dashboard downloads row — full five-artifact set"`

### Task 4: batched PDF lookup + `⋯` download menu in the reviews list

**Files:**
- Modify: `src/malus/repo/repositories.py` (`ArtifactRepo`, after `get` at
  line 338), `src/malus/web/router.py` (`reviews_page`, line 126),
  `src/malus/web/templates/reviews.html`,
  `src/malus/web/static/app.css` (one rule near `.reviews li`, line 181)
- Test: `tests/web/test_reviews_list_downloads.py` (new)

**Interfaces produced:**

```python
class ArtifactRepo:                       # repositories.py
    def review_ids_with(self, kind: str) -> set[int]   # one query, whole page
```

`reviews_page` rows gain `status` and `has_pdf`; finalized rows of
`/ui/reviews` carry a `⋯` menu with the five download links, shown to members
and global admins only.

**Why batched:** `reviews_page` iterates `ReviewRepo(session).list()` — every
review in the instance. Calling `ArtifactRepo(session).get(r, "pdf")` inside
that loop (the shape `review_page` uses for a *single* review, `router.py:339`)
would issue one `review_artifacts` SELECT per row: the classic N+1 that turns
the landing page into the slowest page in the app as the archive grows. One
`SELECT DISTINCT review_id FROM review_artifacts WHERE kind = 'pdf'` answers
the whole page. Scoping it with an `IN (...)` of the listed ids buys nothing
here (the page lists *all* reviews) and costs a variable-length clause, so the
method takes only `kind`.

- [x] **Step 1: failing tests** — create
  `tests/web/test_reviews_list_downloads.py` (self-contained helper: the test
  package has no `__init__.py`, so never import across test modules):

```python
"""v3.1 step 04: /ui/reviews carries the download menu on finalized rows, and
the archived-PDF flag that feeds it comes from ONE batched query — not one per
row (`reviews_page` renders every review in the instance)."""

from __future__ import annotations

from sqlalchemy import event


def _finalize_review(owner, reviewer, review_id: str, docs) -> None:
    """Freeze → comment → harvest → accept → closeout → implement → verify →
    finalize, leaving `review_id` in phase `finalized`."""
    rid = f"{review_id}-0001"
    owner.post("/reviews", json={"review_id": review_id, "rid_prefix": review_id})
    owner.post(f"/reviews/{review_id}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{review_id}/freeze", json={"content": docs["baseline"]})
    reviewer.post(f"/reviews/{review_id}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    owner.post(f"/reviews/{review_id}/harvest")
    owner.post(
        f"/ui/reviews/{review_id}/rids/{rid}/dispose",
        data={"disposition": "accepted", "reply": "ok"},
    )
    reviewer.post(f"/ui/reviews/{review_id}/rids/{rid}/accept")
    owner.post(f"/ui/reviews/{review_id}/start-closeout")
    owner.post(
        f"/ui/reviews/{review_id}/closeout",
        data={"content": docs["baseline"].replace("configurable", "bounded"), "rids": [rid]},
    )
    owner.post(f"/ui/reviews/{review_id}/rids/{rid}/implement", data={"resolution": "bounded"})
    reviewer.post(f"/ui/reviews/{review_id}/rids/{rid}/verify")
    r = owner.post(f"/ui/reviews/{review_id}/finalize", follow_redirects=False)
    assert r.status_code == 303, r.text[:300]


def test_menu_appears_only_on_finalized_rows(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    _finalize_review(owner, f, "REV-A", docs)
    owner.post("/reviews", json={"review_id": "REV-B", "rid_prefix": "REV-B"})
    owner.post("/reviews/REV-B/freeze", json={"content": docs["baseline"]})

    page = owner.get("/ui/reviews").text
    for name in ("baseline.md", "final.md", "diff.html", "report.md"):
        assert f"/ui/reviews/REV-A/download/{name}" in page
    assert "/ui/reviews/REV-B/download/" not in page  # still in review → no menu


def test_non_member_row_carries_no_download_menu(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    _finalize_review(owner, f, "REV-A", docs)
    outsider = mkuser("out", "Out Sider")

    page = outsider.get("/ui/reviews").text
    assert "REV-A" in page                            # the row is listed…
    assert "/ui/reviews/REV-A/download/" not in page  # …without members-only links


def test_pdf_lookup_is_batched_not_one_query_per_row(app, mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    for review_id in ("REV-A", "REV-B", "REV-C"):
        _finalize_review(owner, f, review_id, docs)

    seen: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    engine = app.state.engine  # create_app stores it (api/deps.get_session reads it)
    event.listen(engine, "before_cursor_execute", _record)
    try:
        page = owner.get("/ui/reviews")
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert page.status_code == 200
    hits = [s for s in seen if "review_artifacts" in s.lower()]
    assert len(hits) == 1, f"expected 1 batched artifact query for 3 rows, got {len(hits)}"
```

- [x] **Step 2: run** `python -m pytest tests/web/test_reviews_list_downloads.py -q`
  → **FAIL** (no links in the list; no `review_artifacts` query at all).
- [x] **Step 3a: implement** the repo method in
  `src/malus/repo/repositories.py`, inside `ArtifactRepo` after `get`:

```python
    def review_ids_with(self, kind: str) -> set[int]:
        """Every review id owning an artifact of ``kind``, in ONE query — the
        reviews list renders every review, so a per-row ``get`` would be an
        N+1 (v3.1 step 04). It lists all reviews, so no IN-clause scoping."""
        return set(
            self.s.exec(
                select(ReviewArtifact.review_id).where(ReviewArtifact.kind == kind).distinct()
            ).all()
        )
```

- [x] **Step 3b: implement** `reviews_page` (`src/malus/web/router.py:126`) —
  hoist the repos out of the loop and add the two row fields:

```python
    reviews = ReviewRepo(session)
    copies = ReviewerCopyRepo(session)
    pdf_ids = ArtifactRepo(session).review_ids_with("pdf")  # one query for the page
    rows = []
    for r in reviews.list():
        role = authz.review_role(session, r, user)
        to_comment = False
        if role == Role.REVIEWER.value:  # flag reviews awaiting *my* comment
            mine = next((c for c in copies.list(r) if c.user_id == user.id), None)
            to_comment = mine is None or mine.submitted_at is None
        rows.append(
            {
                "review": r,
                "role": role,
                "to_comment": to_comment,
                "status": r.status,
                "has_pdf": r.id in pdf_ids,
            }
        )
```

- [x] **Step 3c: implement** the menu in
  `src/malus/web/templates/reviews.html`, as the last child of the `<li>`
  (after the title span, line 21). Reuse the dashboard's
  `details.menu` / `.menu-items` pattern verbatim (`review.html:48-54`,
  CSS at `app.css:437-447`) — no new component, no JS:

```html
    {% if row.status == 'finalized' and (row.role or user.is_admin) %}
    {# v3.1 step 04: the results are reachable from where a member starts, not
       only from the dashboard. Members/admin only — the routes 403 otherwise. #}
    <details class="menu row-menu">
      <summary aria-label="Downloads for {{ row.review.review_id_str }}">⋯</summary>
      <div class="menu-items">
        <a href="/ui/reviews/{{ row.review.review_id_str }}/download/baseline.md">baseline.md</a>
        <a href="/ui/reviews/{{ row.review.review_id_str }}/download/final.md">final.md</a>
        <a href="/ui/reviews/{{ row.review.review_id_str }}/download/diff.html">diff.html</a>
        <a href="/ui/reviews/{{ row.review.review_id_str }}/download/report.md">report.md</a>
        {% if row.has_pdf %}
        <a href="/ui/reviews/{{ row.review.review_id_str }}/download/review.pdf">PDF</a>
        {% else %}
        <a href="/ui/reviews/{{ row.review.review_id_str }}/print"
           title="No archived PDF (malus[pdf] not installed at finalize) — use the browser print dialog">Print view</a>
        {% endif %}
      </div>
    </details>
    {% endif %}
```

- [x] **Step 3d: implement** the one styling rule in
  `src/malus/web/static/app.css`, next to the `.reviews` block (line 182):

```css
.reviews li .row-menu { margin-left: auto; }   /* v3.1: downloads menu sits at the row end */
```

  (`.menu` is `position: relative`, so the popup anchors to the summary and is
  not clipped — `.reviews li` sets no `overflow`.)
- [x] **Step 4: run** `python -m pytest tests/web/test_reviews_list_downloads.py -q`
  → **PASS**, then `python -m pytest -q` → green.
- [x] **Step 5: commit**
  `git commit -m "feat(web): download menu on finalized rows of the reviews list"`

## Definition of Done

- [x] Every deliverable checked; `python -m pytest -q` green (the suite must
  pass **with and without** the `malus[pdf]` extra — the fifth slot is
  conditional in both the dashboard row and the list menu).
- [x] The five download routes behave identically at the gate: `200` +
  `Content-Disposition: attachment` + non-empty body for a member of a
  finalized review, `409` before finalize, `403` for a non-member.
- [x] `download/diff.html` opens correctly from `file://` after a real
  browser download: no console errors, no network requests, line numbers and
  colours visible, prints sensibly.
- [x] The batched-query test proves one `review_artifacts` query for three
  finalized rows.
- [x] Manual smoke: `/ui/reviews` shows `⋯` only on finalized rows and only to
  members/admin; the dashboard row reads
  `baseline.md · final.md · diff.html · report.md · PDF`.
- [x] README's finalize step lists the five artifacts.
- [x] Any agreed deviation recorded under a `## Deviations` heading in this
  file.

## Deviations

**1. Task 2's version-ordinal assertion was wrong (`v1`/`v2` → `v1 → v3`).**
The step's test asserted `"v1" in body and "v2" in body` for the exported diff
header. The implementation renders the real ordinals, which are **v1 → v3**, not
v1 → v2: `svc.finalize` calls `add_version(..., is_final=True)`, so a finalized
review has three versions — v1 the frozen baseline, v2 the closeout save, v3 the
final. (This is the same behaviour v3.1 step 02 pins in
`test_re_terminate_after_reopen_adds_a_second_final_version`.) The assertion now
reads `assert "Baseline v1 → final v3" in body`, which checks the header carries
the ordinals *and* documents why the final one is v3. No production code changed.

**2. `.diff-ln-new` has no rule in the standalone export.** `app.css` gives it
`border-right` + `margin-right` as a visual separator between the gutters and
the text; `diff_download.html`'s inline CSS, as specified by this step, styles
only `.diff-ln`. Verified in a browser: the export reads correctly without it
(`.diff-ln`'s `padding-right` keeps the columns apart), so the template ships as
the step wrote it. Noted only because the export therefore looks marginally
different from the in-app `?view=full` page. `.diff-hunk` and `.diff-ln-old`
have no rule in `app.css` either — those are structural, by design.

**Verification notes** (not deviations):

- The DoD's "green with **and without** `malus[pdf]`" was run both ways: 506
  passed / 1 skipped without the extra, **508 passed / 0 skipped** with it. On
  this machine weasyprint needs `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`
  to find Homebrew's Pango, otherwise `PDF_AVAILABLE` is silently `False`.
- `download/diff.html` was downloaded through the real route and rendered from a
  bare static server with no application behind it:
  `performance.getEntriesByType('resource')` reported **0** sub-resources, the
  console was clean, gutters and colours applied, and the `@media print` block
  was present. (The browser tool would not open a `file://` path directly; a
  static-reference audit of the saved file — no `<script>`, no `src=`, no
  `<link>`, no `/static/`, no `http(s)://`, no `@import`, no `url()` — closes
  that gap.)

## Out of scope

- The `?view=Compact|Full` toggle on `/ui/reviews/{id}/diff` and the
  `html_diff` signature change itself — v3.1 step 03.
- Terminate/reopen wording and the admin reopen entry — v3.1 step 02.
- Any change to `_member_finalized`'s policy (members or global admin,
  finalized only) — the two new routes adopt it unchanged.
- Hardening the `Content-Disposition` filename against a review id containing
  a quote: all five routes share the existing v3 pattern, so a change belongs
  in one separate commit, not here.
- Bundling the five artifacts into a single archive, and any release chore
  (version bump, CHANGELOG) — v3 step 06.
