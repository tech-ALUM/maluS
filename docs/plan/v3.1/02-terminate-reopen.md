# v3.1 Step 2 — Terminate & reopen

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** make the end of a review reachable. The owner's button reads
**Terminate review** (dashboard and, once step 01 lands, the document's closeout
toolbar), and a terminated review is no longer a dead end: a **human global
admin** can push it back to `closeout` from the dashboard `⋯` menu, behind a
double confirm and an audit row.

**Architecture:** the domain vocabulary is untouched — the phase stays
`finalized`, the service stays `svc.finalize`, the route stays
`POST /ui/reviews/{id}/finalize`, and ADR / `docs/spec/` / CHANGELOG wording
stays as written (v3.1 design, "Terminate" row). Only the **user-facing label
and confirm string** change. The reverse transition is a new service
`svc.reopen_finalized` (`finalized → closeout`) modelled one-for-one on
`svc.reopen_review` (`src/malus/services/core.py:889`, the existing
`closeout → in_review` admin escape hatch): the guard lives in the service —
like `svc.purge_rid` (`core.py:374`) — and is *repeated* in the route, so a
future caller (CLI, MCP, API) cannot bypass it.

**Why re-terminating after a reopen is safe (verified in code):**

- `svc.finalize` (`core.py:934`) calls `VersionRepo.add_version(..., is_final=True)`
  — so a second termination adds a **new** `is_final` version; the superseded
  one stays in history. `VersionRepo.latest` (`src/malus/repo/repositories.py:202`)
  orders `DocumentVersion.ordinal.desc()`, so `download/final.md` and the
  closeout sheet both serve the newest.
- `svc.finalize` also archives a **new** `pdf` artifact via `ArtifactRepo.add`.
  `ArtifactRepo.get` (`src/malus/repo/repositories.py:338`) reads
  `.order_by(ReviewArtifact.created.desc(), ReviewArtifact.id.desc())` and takes
  `.first()` — the newest artifact wins, the older one is inert history.
- No RID status changes on reopen: `reopen_finalized` is a phase action only.
  The `finalize_gate` (`core.py:911`) therefore still holds right after a
  reopen, and the owner can terminate again without re-verifying anything.

**Tech stack:** Python 3.12+, SQLModel, FastAPI, Jinja. No JS. Depends on v3
step 04 (finalize + downloads, `main` = 2df818c). Task 5 additionally depends on
v3.1 step 01 — see its header.

## Global constraints

- Python 3.12+; **no new runtime dependencies** (PyYAML + Typer + FastAPI/SQLModel
  only, per `CLAUDE.md` / ADR 0002) and **no new vendored JS** (ADR 0003 untouched).
- The **closure-authority invariant is untouched**: `reopen_finalized` is an
  admin *phase* action, not a closure verdict — it issues no verdict on any RID —
  and it carries the same absolute `is_ai` bar as every closure action.
  Owner: never. AI principal (even an AI global admin): never.
- Domain vocabulary frozen: phase value `finalized`, service name `finalize`,
  route `/finalize`, audit action `finalize`, ADR/spec/CHANGELOG text. Only the
  button label and its `confirm()` string are edited.
- Conventional Commits, one commit per task.
- `python -m pytest -q` green at the end of **every** task.

## Deliverables

- [x] Dashboard button relabelled `Terminate review` + new confirm text (`review.html`)
- [x] `svc.reopen_finalized` — `finalized → closeout`, human-global-admin-only, audited
- [x] `POST /ui/reviews/{review_id}/reopen-terminated` — 303 admin / 403 owner /
      403 AI admin / 409 wrong phase
- [x] `⋯`-menu entry on a terminated review, human admin only, double confirm
- [x] `Terminate review` in the document closeout toolbar when the gate holds
      (**needs step 01** — skippable, see Task 5)
- [x] Full suite green

---

### Task 1: relabel Finalize → Terminate (dashboard)

**Files:**
- Modify: `src/malus/web/templates/review.html` (the owner actions block, lines 35-40)
- Modify: `tests/web/test_finalize_downloads.py` (existing assertions at lines 61 and 69)

- [x] **Step 1: failing test** — in `tests/web/test_finalize_downloads.py`, first
  retarget the two existing label assertions:

```python
    # line 61, in test_finalize_blocked_until_gate_holds
    assert "Terminate review" not in owner.get(f"/ui/reviews/{R}").text
```

```python
    # line 69, in test_finalize_flow_and_downloads
    assert "Terminate review" in page  # gate satisfied → button appears
```

  then append a new test that pins the label *and* the unchanged plumbing:

```python
def test_dashboard_button_reads_terminate_review(mkuser, docs):
    """v3.1 step 02: user-facing wording only — phase, service and route keep
    the `finalize` vocabulary."""
    owner, _f = _to_closeout(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}").text
    assert "Terminate review" in page
    assert "Finalize review" not in page
    assert "Terminate the review?" in page                 # new confirm text
    assert f'action="/ui/reviews/{R}/finalize"' in page    # route unchanged
```

- [x] **Step 2:** `python -m pytest -q tests/web/test_finalize_downloads.py` → FAIL
  (3 failures: the page still says "Finalize review").
- [x] **Step 3: implement** — replace lines 35-40 of
  `src/malus/web/templates/review.html` with:

```html
    {% if finalize_ready %}
    <form method="post" action="/ui/reviews/{{ review.review_id_str }}/finalize" class="inline"
          onsubmit="return confirm('Terminate the review? The last document version becomes final, the PDF is archived, and no further changes are possible (only a global admin can reopen it).')">
      <button class="primary">Terminate review</button>
    </form>
    {% endif %}
```

  Nothing else moves: `finalize_ready` still comes from `router.py:336-338`, the
  form still posts to `/finalize`.
- [x] **Step 4:** `python -m pytest -q` → PASS.
- [x] **Step 5:** `git commit -m "feat(web): the owner's button reads \"Terminate review\""`

### Task 2: `svc.reopen_finalized`

**Files:**
- Modify: `src/malus/services/core.py` (new function right after `reopen_review`, line 897)
- Modify: `src/malus/services/__init__.py` (import list + `__all__`)
- Modify: `src/malus/db/models.py` (the `ReviewStatus.FINALIZED` docstring bullet, line 46)
- Test: `tests/services/test_phases.py` (new section after the `reopen_review` one, line 198)

**Interfaces produced:**

```python
def reopen_finalized(session: Session, review: Review, *, by=None) -> Review
    """finalized -> closeout. Human global admin only; audited."""
```

- [x] **Step 1: failing tests** — extend the imports at the top of
  `tests/services/test_phases.py`:

```python
from sqlmodel import Session, select

from malus.db.models import AuditLog, ReviewStatus
from malus.models import ClosureAuthorityError
```

  and append:

```python
# --------------------------------------------------------------------------- #
# reopen_finalized (v3.1 step 02): the admin undo of Terminate, FINALIZED ->
# CLOSEOUT. A phase action, not a closure verdict — but the is_ai bar is the
# same absolute one.
# --------------------------------------------------------------------------- #


@pytest.fixture
def human_admin(session: Session):
    user = UserRepo(session).get_or_create("SU Admin")
    user.is_admin = True
    session.add(user)
    session.flush()
    return user


@pytest.fixture
def ai_admin(session: Session):
    user = UserRepo(session).get_or_create("AI Admin")
    user.is_admin = True
    user.is_ai = True
    session.add(user)
    session.flush()
    return user


def _terminated(session: Session, review_with_rids, owner):
    review = review_with_rids(statuses=["verified"])
    svc.start_closeout(session, review, by=owner)
    assert svc.finalize(session, review, by=owner) == []
    assert review.status == ReviewStatus.FINALIZED.value
    return review


def test_reopen_finalized_returns_to_closeout(session, review_with_rids, owner, human_admin):
    review = _terminated(session, review_with_rids, owner)
    svc.reopen_finalized(session, review, by=human_admin)
    assert review.status == ReviewStatus.CLOSEOUT.value


def test_reopen_finalized_requires_finalized_phase(session, review_with_rids, owner, human_admin):
    review = review_with_rids(statuses=["verified"])
    svc.start_closeout(session, review, by=owner)
    with pytest.raises(svc.PhaseError):
        svc.reopen_finalized(session, review, by=human_admin)
    assert review.status == ReviewStatus.CLOSEOUT.value


def test_reopen_finalized_refuses_the_owner(session, review_with_rids, owner):
    review = _terminated(session, review_with_rids, owner)
    with pytest.raises(ClosureAuthorityError):
        svc.reopen_finalized(session, review, by=owner)
    assert review.status == ReviewStatus.FINALIZED.value


def test_reopen_finalized_refuses_an_ai_admin(session, review_with_rids, owner, ai_admin):
    review = _terminated(session, review_with_rids, owner)
    with pytest.raises(ClosureAuthorityError):
        svc.reopen_finalized(session, review, by=ai_admin)
    assert review.status == ReviewStatus.FINALIZED.value


def test_reopen_finalized_refuses_an_anonymous_caller(session, review_with_rids, owner):
    review = _terminated(session, review_with_rids, owner)
    with pytest.raises(ClosureAuthorityError):
        svc.reopen_finalized(session, review)  # by=None
    assert review.status == ReviewStatus.FINALIZED.value


def test_reopen_finalized_is_audited(session, review_with_rids, owner, human_admin):
    review = _terminated(session, review_with_rids, owner)
    svc.reopen_finalized(session, review, by=human_admin)
    entry = session.exec(select(AuditLog).where(AuditLog.action == "reopen_finalized")).one()
    assert entry.target == f"review:{review.review_id_str}"
    assert entry.actor.display_name == "SU Admin"


def test_re_terminate_after_reopen_adds_a_second_final_version(
    session, review_with_rids, owner, human_admin
):
    """The superseded final version stays in history; `latest` (ordinal desc)
    and `ArtifactRepo.get` (created desc) both serve the newest."""
    review = _terminated(session, review_with_rids, owner)
    svc.reopen_finalized(session, review, by=human_admin)
    svc.save_closeout_version(
        session, review, "# doc after the reopen\n", rid_ids=[RID_ID], by=owner
    )
    assert svc.finalize(session, review, by=owner) == []
    assert review.status == ReviewStatus.FINALIZED.value
    latest = VersionRepo(session).latest(review)
    assert latest.is_final and latest.content == "# doc after the reopen\n"
```

  The last test also needs `VersionRepo` in the repo import at line 19:
  `from malus.repo import ReviewRepo, RidRepo, UserRepo, VersionRepo`.

- [x] **Step 2:** `python -m pytest -q tests/services/test_phases.py` → FAIL
  (`AttributeError: module 'malus.services' has no attribute 'reopen_finalized'`).
- [x] **Step 3: implement** — in `src/malus/services/core.py`, immediately after
  `reopen_review` (i.e. after line 897, before the `report, finalize` banner):

```python
def reopen_finalized(session: Session, review: Review, *, by=None) -> Review:
    """Admin escape hatch (v3.1): ``finalized -> closeout``.

    Terminating a review is no longer a dead end — a **human global admin**
    (never the owner, never an AI principal: the ``is_ai`` bar is absolute) can
    put it back into closeout so the owner fixes what a late read found. This is
    a *phase* action, not a closure verdict: no RID changes status, so the
    ``finalize_gate`` still holds and the review can be terminated again. The
    superseded ``is_final`` version stays in history; re-terminating adds a new
    final version and a new ``pdf`` artifact — ``VersionRepo.latest`` orders by
    ordinal and ``ArtifactRepo.get`` by ``created`` desc, so the newest wins.

    The route gates on the same rule; re-checked here (defense-in-depth), like
    ``purge_rid``."""
    _forbid_ai_commit(by)
    if by is None or not getattr(by, "is_admin", False):
        raise ClosureAuthorityError(
            "only a human global admin may reopen a terminated review"
        )
    _require_phase(review, ReviewStatus.FINALIZED)
    ReviewRepo(session).set_status(review, ReviewStatus.CLOSEOUT.value)
    AuditRepo(session).log(
        action="reopen_finalized", target=f"review:{review.review_id_str}", actor=by
    )
    return review
```

  Order matters and is deliberate: `_forbid_ai_commit` first (403, the absolute
  AI bar, same message as everywhere else), then the admin check (403), then
  `_require_phase` (409 via the `TransitionError` handler,
  `src/malus/api/errors.py:33`).

  Export it in `src/malus/services/__init__.py` — add `reopen_finalized,` to the
  `from malus.services.core import (...)` block (alphabetically after
  `reopen_review`, line 31) and `"reopen_finalized",` to `__all__` (after
  `"reopen_review"`, line 73).

  Keep the phase enum honest — `src/malus/db/models.py` line 46:

```python
    - ``FINALIZED``: the closing document + minutes are produced
      (``services.core.finalize``). Terminal for everyone except a human global
      admin, who may ``reopen_finalized`` back to ``CLOSEOUT`` (v3.1).
```

- [x] **Step 4:** `python -m pytest -q` → PASS.
- [x] **Step 5:** `git commit -m "feat(svc): reopen_finalized — human-admin undo of a terminated review"`

### Task 3: the route

**Files:**
- Modify: `src/malus/web/router.py` (right after `finalize_action`, line 1094)
- Test: `tests/web/test_finalize_downloads.py` (extend)

**Interfaces produced:** `POST /ui/reviews/{review_id}/reopen-terminated` —
human global admin only; 303 → `/ui/reviews/{review_id}`.

- [x] **Step 1: failing tests** — append to `tests/web/test_finalize_downloads.py`:

```python
def test_reopen_terminated_is_human_admin_only(mkuser, docs):
    owner, f = _to_closeout(mkuser, docs)
    ai_admin = mkuser("aiadmin", "AI Admin", is_ai=True, is_admin=True)
    assert owner.post(f"/ui/reviews/{R}/finalize", follow_redirects=False).status_code == 303

    for client in (owner, f, ai_admin):  # owner: never; AI admin: is_ai is absolute
        assert client.post(
            f"/ui/reviews/{R}/reopen-terminated", follow_redirects=False
        ).status_code == 403
    assert owner.get(f"/reviews/{R}").json()["status"] == "finalized"  # untouched


def test_reopen_terminated_admin_flips_back_to_closeout_and_audits(app, mkuser, docs, admin):
    owner, _f = _to_closeout(mkuser, docs)
    owner.post(f"/ui/reviews/{R}/finalize")
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})

    r = admin.post(f"/ui/reviews/{R}/reopen-terminated", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith(f"/ui/reviews/{R}")
    assert owner.get(f"/reviews/{R}").json()["status"] == "closeout"

    from sqlmodel import Session, select

    from malus.db.models import AuditLog

    with Session(app.state.engine) as s:
        entry = s.exec(select(AuditLog).where(AuditLog.action == "reopen_finalized")).one()
        assert entry.target == f"review:{R}" and entry.actor.username == "admin"


def test_reopen_terminated_wrong_phase_is_409(mkuser, docs, admin):
    _owner, _f = _to_closeout(mkuser, docs)  # closeout, never terminated
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    assert admin.post(
        f"/ui/reviews/{R}/reopen-terminated", follow_redirects=False
    ).status_code == 409


def test_re_terminate_after_reopen_supersedes_final_and_pdf(app, mkuser, docs, admin):
    """The v3.1 design claim, end to end: history keeps both finals, the
    downloads serve the newest (VersionRepo.latest / ArtifactRepo.get)."""
    owner, _f = _to_closeout(mkuser, docs)
    owner.post(f"/ui/reviews/{R}/finalize")
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    admin.post(f"/ui/reviews/{R}/reopen-terminated")

    second = FINAL_MD + "\nAdded after the reopen.\n"
    assert owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": second, "rids": ["SIN-SRS-0001"]},
        follow_redirects=False,
    ).status_code == 303
    assert owner.post(f"/ui/reviews/{R}/finalize", follow_redirects=False).status_code == 303
    assert owner.get(f"/ui/reviews/{R}/download/final.md").text == second

    from sqlmodel import Session, select

    from malus.db.models import DocumentVersion, ReviewArtifact

    from malus import pdfgen

    with Session(app.state.engine) as s:
        finals = s.exec(
            select(DocumentVersion).where(DocumentVersion.is_final == True)  # noqa: E712
        ).all()
        assert len(finals) == 2  # the superseded final stays in history
        if pdfgen.PDF_AVAILABLE:
            pdfs = s.exec(select(ReviewArtifact).where(ReviewArtifact.kind == "pdf")).all()
            assert len(pdfs) == 2
```

- [x] **Step 2:** `python -m pytest -q tests/web/test_finalize_downloads.py` → FAIL
  (405/404 on the unknown route).
- [x] **Step 3: implement** — in `src/malus/web/router.py`, after `finalize_action`
  (line 1094):

```python
@web.post("/ui/reviews/{review_id}/reopen-terminated")
def reopen_terminated_action(
    review_id: str, request: Request, session: Session = Depends(get_session)
):
    """Admin escape hatch (v3.1): ``finalized -> closeout``, the undo of
    Terminate. Reserved to a human global admin — not the owner, not a
    moderator, never an AI. ``svc.reopen_finalized`` re-checks both bars, and
    raises ``PhaseError`` (-> 409) when the review is not terminated."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if not (user.is_admin and not user.is_ai):
        raise HTTPException(
            status_code=403,
            detail="reopening a terminated review is a human global-admin-only action",
        )
    svc.reopen_finalized(session, review, by=user)
    return RedirectResponse(f"/ui/reviews/{review_id}", 303)
```

  Mirrors `reopen_review_action` (`router.py:535`) exactly; the 409 comes for
  free from the `TransitionError` handler.
- [x] **Step 4:** `python -m pytest -q` → PASS.
- [x] **Step 5:** `git commit -m "feat(web): POST /reopen-terminated — admin route back to closeout"`

### Task 4: the `⋯`-menu entry

**Files:**
- Modify: `src/malus/web/templates/review.html` (the `<details class="menu">` block, lines 48-54)
- Test: `tests/web/test_finalize_downloads.py` (extend)

- [x] **Step 1: failing test** — append to `tests/web/test_finalize_downloads.py`:

```python
def test_reopen_entry_shows_only_for_a_human_admin_on_a_terminated_review(mkuser, docs, admin):
    owner, _f = _to_closeout(mkuser, docs)
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})

    assert "/reopen-terminated" not in admin.get(f"/ui/reviews/{R}").text  # closeout: not yet

    owner.post(f"/ui/reviews/{R}/finalize")
    page = admin.get(f"/ui/reviews/{R}").text
    assert "/reopen-terminated" in page and "Reopen terminated review" in page
    assert "Reopen this terminated review?" in page   # first confirm
    assert "Really reopen" in page                    # second confirm

    assert "/reopen-terminated" not in owner.get(f"/ui/reviews/{R}").text  # owner: never
    ai_admin = mkuser("aiadmin", "AI Admin", is_ai=True, is_admin=True)
    assert "/reopen-terminated" not in ai_admin.get(f"/ui/reviews/{R}").text  # is_ai bar
```

- [x] **Step 2:** `python -m pytest -q tests/web/test_finalize_downloads.py` → FAIL.
- [x] **Step 3: implement** — in `src/malus/web/templates/review.html`, inside
  `<div class="menu-items">` (line 50), between the "Copy review link" button and
  the "Delete review" link:

```html
      {% if phase == 'finalized' and user.is_admin and not user.is_ai %}
      <form method="post" action="/ui/reviews/{{ review.review_id_str }}/reopen-terminated" class="inline"
            onsubmit="return confirm('Reopen this terminated review? It goes back to closeout and the owner can edit the document again.') &amp;&amp; confirm('Really reopen {{ review.review_id_str }}? The current final version and PDF stay in history, but terminating again produces new ones.')">
        <button class="linkbtn menu-danger">Reopen terminated review</button>
      </form>
      {% endif %}
```

  Double confirm = the "Submit copy" idiom (`document.html:81`) and the purge
  idiom (`static/document-viewer.js:483-484`). `&amp;&amp;` because this is an
  HTML attribute. The surrounding `<p class="actions">` is already gated on
  `role == 'owner' or user.is_admin` (line 18), so a plain reviewer never
  reaches the menu at all.
- [x] **Step 4:** `python -m pytest -q` → PASS.
- [x] **Step 5:** `git commit -m "feat(web): reopen a terminated review from the dashboard ⋯ menu"`

### Task 5: Terminate in the document closeout toolbar — **depends on step 01**

> **Dependency:** the closeout toolbar in the document viewer is built by
> `docs/plan/v3.1/01-closeout-in-document.md`. If step 01 is **not merged yet**,
> **skip this task** — tasks 1-4 are complete and shippable on their own — and
> come back to it after 01 lands. The fallback below exists only if you are told
> to ship it standalone.

**Files:**
- Modify: `src/malus/web/router.py` (`_document_context`, the return at line 795)
- Modify: `src/malus/web/templates/document.html` (step 01's closeout toolbar)
- Test: `tests/web/test_finalize_downloads.py` (extend)

- [x] **Step 1: failing tests** — append to `tests/web/test_finalize_downloads.py`:

```python
def test_document_offers_terminate_when_the_gate_holds(mkuser, docs):
    owner, f = _to_closeout(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}/document").text
    assert "Terminate review" in page
    assert f'action="/ui/reviews/{R}/finalize"' in page
    # a reviewer never terminates (the toolbar form is canDispose-gated)
    assert "Terminate review" not in f.get(f"/ui/reviews/{R}/document").text


def test_document_hides_terminate_until_the_gate_holds(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "M. Mod", "role": "moderator"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    mod.post(f"/reviews/{R}/harvest")
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "ok"},
    )
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    owner.post(f"/ui/reviews/{R}/start-closeout")  # accepted RID not yet verified
    assert "Terminate review" not in owner.get(f"/ui/reviews/{R}/document").text
```

- [x] **Step 2:** `python -m pytest -q tests/web/test_finalize_downloads.py` → FAIL
  (the document page has no Terminate button).
- [x] **Step 3: implement.**

  a) `src/malus/web/router.py` — in `_document_context`, just before the return
  at line 795 (the gate is only computed in closeout, so no cost elsewhere):

```python
    finalize_ready = review.status == ReviewStatus.CLOSEOUT.value and not svc.finalize_gate(
        session, review
    )
    return {
        "user": user,
        "review": review,
        "role": role,
        "data": data,
        "error": error,
        "finalize_ready": finalize_ready,
    }
```

  It is a Jinja-only flag — deliberately **not** added to `data`, so the
  `#viewer-data` payload and its snapshot assertions stay untouched.

  b) `src/malus/web/templates/document.html` — inside step 01's closeout toolbar
  (the element holding the `Render | Edit` buttons), after the toggle:

```html
    {% if finalize_ready and data.canDispose %}
    <form method="post" action="/ui/reviews/{{ review.review_id_str }}/finalize" class="inline"
          onsubmit="return confirm('Terminate the review? The last document version becomes final, the PDF is archived, and no further changes are possible (only a global admin can reopen it).')">
      <button class="primary">Terminate review</button>
    </form>
    {% endif %}
```

  Same label and same confirm string as Task 1 — keep them byte-identical.
  `data.canDispose` (`router.py:786`) is already `(owner or admin) and not is_ai`.

  **Fallback if step 01 is not merged** and you were told to ship anyway: put the
  same `<form>` inside a new `<p class="actions">` right after
  `<h1>Document …</h1>` (`document.html:6`), wrapping it in
  `{% if data.phase == 'closeout' %}…{% endif %}` as well. When step 01 lands,
  move the form into its toolbar and delete the wrapper.
- [x] **Step 4:** `python -m pytest -q` → PASS.
- [x] **Step 5:** `git commit -m "feat(web): Terminate review in the document closeout toolbar"`

## Definition of Done

- [x] Every deliverable above checked (Task 5 may be deferred with step 01 —
      record it under `## Deviations` if so).
- [x] `python -m pytest -q` green, exit 0.
- [x] `grep -rn "Finalize review" src/ docs/adr docs/spec` returns nothing in
      `src/`, and `grep -rn "finalize" src/malus/services/core.py` still shows
      the service, gate, route and audit action named `finalize` — the rename is
      label-only.
- [x] Manual smoke (browser): **partially run — see `## Deviations` #2.** Done
      in a real browser against a seeded review: the dashboard shows **Terminate
      review**; the document's toolbar button fires its confirm, and posting
      flips the phase to `finalized`. The admin `⋯` reopen, the re-terminate and
      the downloads were **not** driven by hand — they are plain server-rendered
      forms with no JS, and each is pinned by an automated test
      (`test_reopen_entry_shows_only_for_a_human_admin_on_a_terminated_review`,
      `test_reopen_terminated_admin_flips_back_to_closeout_and_audits`,
      `test_re_terminate_after_reopen_supersedes_final_and_pdf`).
- [x] No new dependency in `pyproject.toml`, no new file under
      `src/malus/web/static/vendor/`.

## Deviations

Agreed with Francesco Miccoli during implementation, 2026-07-30.

**1. Task 5 — Terminate in the document toolbar is a `post()` button, not a
`<form>`.** The step's snippet nests a `<form>` inside the closeout toolbar, but
step 01 put `.doc-toolbar` *inside* `<form id="rev-form">`
(`document.html:68-103`). HTML forbids nested forms: the parser drops the inner
tag, and the Terminate button would have become a submit button of `#rev-form` —
posting the **closeout save** instead of finalizing. This is the same limit step
01 hit with *Mark implemented*, and it is resolved the same way: a
`<button type="button" id="doc-terminate">` in the toolbar, wired in
`document-viewer.js` to the existing detached-form `post()` helper.

Everything the step specified is preserved — toolbar placement, the
`finalize_ready and data.canDispose` gate, the label, the confirm string and the
`/finalize` route. The confirm text lives in a `data-confirm` attribute rather
than an `onsubmit=`, so it still sits in the template beside the dashboard's copy
and stays greppable; `test_document_and_dashboard_share_the_terminate_confirm`
pins the two byte-identical, and `test_document_terminate_is_not_a_nested_form`
pins that no `<form>` is ever nested in `#rev-form`.

Options considered and rejected: moving `.doc-toolbar` out of `#rev-form`
(restructures freshly-landed step 01 markup), and the step's own "01 not merged"
fallback of a separate `<p class="actions">` (valid, but drops the button out of
the toolbar the design asked for).

**2. Manual smoke is partial.** Run in a real browser: the dashboard Terminate
button renders once the gate holds, and the document toolbar button fires its
confirm and — on accept — posts `/finalize`, flipping the phase to `finalized`.
That was the point of the exercise: the JS wiring introduced by deviation #1 is
the one thing this repo's test suite cannot cover (no JS harness, per the kickoff
prompt). The remaining smoke items (admin `⋯` reopen with its double confirm,
re-terminate, `download/final.md` serving the second text, PDF) were left to
their automated tests — all are server-rendered forms with no JavaScript.

Two incidental findings, both **out of scope** for this step and neither a
regression from it:

- `malus serve` sets `https_only=True` with no override, so a plain-HTTP local
  session cannot log in through the GUI. Correct by design — production runs
  behind Caddy TLS (`docker-compose.yml:17`) — but it means a local browser
  smoke needs `create_app(..., https_only=False)`.
- `pyproject.toml` pins `mcp>=1.2`, which now resolves to `mcp` 2.x, where
  `mcp.server.fastmcp` no longer exists; a clean `pip install -e ".[dev,mcp]"`
  leaves `tests/mcp/test_mcp.py` failing until `mcp<2` is pinned.

## Out of scope

- The closeout workspace inside the document viewer, the queue panel and the
  Render/Edit toggle — step 01.
- `html_diff(context=None, line_numbers=…)` and the `Compact | Full` toggle,
  plus the duplicate dashboard `Full diff` button — step 03.
- `download/baseline.md`, `download/diff.html` and the `⋯` menu in the reviews
  list — step 04.
- Any change to the RID state machine, the closure-authority rules, the phase
  values, or the signing/attestation ideas of v3 step 05.

## Sources

- `docs/plan/v3.1/00-design.md` — Decisions table, rows *Terminate* and *Reopen
  a terminated review*; Steps table row 2; "What does not change".
- Code read while writing this step: `src/malus/services/core.py:77` (`_require_phase`),
  `:86` (`_forbid_ai_commit`), `:374` (`purge_rid`, the service-side admin guard
  idiom), `:889` (`reopen_review`), `:911` (`finalize_gate`), `:934` (`finalize`),
  `:800-831` (`save_closeout_version`); `src/malus/repo/repositories.py:174`
  (`add_version`), `:202` (`latest`), `:338` (`ArtifactRepo.get`, `created desc`);
  `src/malus/web/router.py:250` (`review_page`), `:334-342` (`phase`,
  `finalize_ready`, `has_pdf`), `:535` (`reopen_review_action`), `:678-795`
  (`_document_context`), `:1081` (`finalize_action`);
  `src/malus/web/templates/review.html:18-56`;
  `src/malus/web/templates/document.html:81` (double-confirm idiom);
  `src/malus/web/static/document-viewer.js:480-484` (purge double confirm);
  `src/malus/api/authz.py:28-84`; `src/malus/api/errors.py` (403/409 mapping);
  `src/malus/db/models.py:32-53` (`ReviewStatus`);
  `tests/web/conftest.py` (`mkuser`, `docs`, `admin` fixtures),
  `tests/web/test_finalize_downloads.py`, `tests/web/test_admin_superuser.py:96`
  (AI-admin fixture idiom), `tests/services/test_phases.py`.
- `CLAUDE.md` — one step at a time, Conventional Commits, pytest DoD,
  no third-party runtime dependency without a recorded decision.
