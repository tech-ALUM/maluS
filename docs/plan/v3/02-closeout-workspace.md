# v3 Step 2 — Closeout workspace (owner)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** replace the v2 `/implement` page with a closeout workspace at
`/ui/reviews/{id}/closeout`: a work queue of accepted RIDs + the MD editor where
every save declares which RIDs it resolves (`RidChange`), and *Mark implemented*
is an explicit per-RID action.

**Architecture:** evolution of `implement.html` + `editor.js` (spec
§Closeout workspace, §Edit↔RID linkage). No new libraries; server-side rendering,
same services + authz. Depends on step 01 (phases, `closed` status).

**Tech stack:** FastAPI/Jinja, vanilla JS, pytest.

## Global constraints

- Every save must reference ≥1 accepted RID and actually change the text —
  otherwise 422 (spec: *"every document edit is comment-traceable by construction"*).
- Saving links versions; it never advances status. `closed→implemented` happens
  only via the explicit Mark implemented button (spec §Edit↔RID linkage).
- Owner/admin only, human only, phase `closeout` only.
- Suite green + commit at the end of every task.

## Deliverables

- [ ] `save_closeout_version` service (link-only save with validation)
- [ ] Closeout page: work queue + editor + per-RID Mark implemented
- [ ] `/implement` route replaced (301/303 to `/closeout`)
- [ ] Dashboard + viewer link to the workspace in closeout phase
- [ ] Full suite green

---

### Task 1: `save_closeout_version` service

**Files:**
- Modify: `src/malus/services/core.py` (beside `save_version` / `link_change` :563-579)
- Test: `tests/services/test_closeout_workspace.py` (new)

**Interfaces produced:**

```python
def save_closeout_version(
    session, review, content: str, *, rid_ids: list[str], by=None
) -> DocumentVersion
# raises PhaseError (wrong phase), ValueError (no rids / unknown or non-accepted
# rid / unchanged content)
```

- [ ] **Step 1: failing tests** (fixtures per step 01's `tests/services/test_phases.py`):

```python
def test_save_requires_a_rid(closeout_review):
    with pytest.raises(ValueError):
        svc.save_closeout_version(session, closeout_review, "# doc v2", rid_ids=[], by=owner)


def test_save_rejects_unchanged_content(closeout_review):
    latest = VersionRepo(session).latest(closeout_review)
    with pytest.raises(ValueError):
        svc.save_closeout_version(session, closeout_review, latest.content,
                                  rid_ids=[ACCEPTED_RID], by=owner)


def test_save_rejects_non_accepted_rid(closeout_review):
    with pytest.raises(ValueError):
        svc.save_closeout_version(session, closeout_review, "# doc v2",
                                  rid_ids=[REJECTED_RID], by=owner)


def test_save_links_every_selected_rid(closeout_review):
    version = svc.save_closeout_version(session, closeout_review, "# doc v2",
                                        rid_ids=[RID_A, RID_B], by=owner)
    for rid in (RID_A, RID_B):
        row = RidRepo(session).get(closeout_review, rid)
        assert any(c.version_id == version.id for c in RidRepo(session).changes_for(row))
        assert row.status == "closed"          # saving does NOT advance status


def test_save_forbidden_in_review_phase(in_review_review):
    with pytest.raises(svc.PhaseError):
        svc.save_closeout_version(session, in_review_review, "# doc v2",
                                  rid_ids=[RID_A], by=owner)
```

- [ ] **Step 2:** run → FAIL. **Step 3: implement:**

```python
def save_closeout_version(
    session: Session,
    review: Review,
    content: str,
    *,
    rid_ids: list[str],
    by=None,
) -> DocumentVersion:
    """One closeout edit: a new version linked to the accepted RIDs it resolves
    (v3). Traceability by construction: no RIDs → no save; unchanged text → no
    save. Never advances a RID's status (Mark implemented is explicit)."""
    _forbid_ai_commit(by)
    _require_phase(review, ReviewStatus.CLOSEOUT)
    if not rid_ids:
        raise ValueError("a closeout save must resolve at least one accepted RID")
    latest = VersionRepo(session).latest(review)
    if latest is not None and latest.content == content:
        raise ValueError("no changes to save")
    rows = []
    for rid_id in rid_ids:
        row = RidRepo(session).get(review, rid_id)
        if row is None:
            raise ValueError(f"no such RID: {rid_id}")
        if row.disposition != Disposition.ACCEPTED.value:
            raise ValueError(f"{rid_id} is not an accepted finding")
        rows.append(row)
    version = VersionRepo(session).add_version(review, content, by=by)
    for row in rows:
        RidRepo(session).add_change(row, version)
    AuditRepo(session).log(
        action="save_closeout_version",
        target=f"review:{review.review_id_str}",
        actor=by,
        detail={"ordinal": version.ordinal, "rids": [r.rid_str for r in rows]},
    )
    return version
```

- [ ] **Step 4:** run → PASS. **Step 5:** `git commit -m "feat(services): closeout save — version linked to accepted RIDs"`

### Task 2: closeout page (routes + template)

**Files:**
- Modify: `src/malus/web/router.py` (replace `implement_page`/`implement_submit` :767-815)
- Create: `src/malus/web/templates/closeout.html` (from `implement.html`)
- Delete: `src/malus/web/templates/implement.html`
- Modify: `src/malus/web/static/app.css` (queue styles), `src/malus/web/templates/review.html` (workspace link — set in step 01, retarget to `/closeout`)
- Test: `tests/web/test_closeout_page.py` (new)

**Interfaces produced:** `GET/POST /ui/reviews/{id}/closeout`;
`POST /ui/reviews/{id}/rids/{rid}/implement`; `GET /ui/reviews/{id}/implement` → 303 to `/closeout`.

- [ ] **Step 1: failing tests** covering: GET as owner in closeout → 200 with the
  queue groups and editor; GET as reviewer → 403; GET in `in_review` phase → 409;
  POST save with ticked RIDs → 303 and a linked version exists; POST save without
  RIDs → 422 with the error re-rendered; POST `…/rids/{rid}/implement` with a
  linked change → 303 and status `implemented`, without → 422; legacy
  `/implement` GET → 303 to `/closeout`.
- [ ] **Step 2:** run → FAIL. **Step 3: implement:**

  Routes (replacing the v2 pair):

```python
def _closeout_context(session, request, user, review, *, error=None):
    latest = VersionRepo(session).latest(review)
    rtd = svc.export(session, review)
    accepted = [r for r in rtd.rids if r.disposition is Disposition.ACCEPTED]
    changed_rids = {  # rids that already have a post-baseline linked change
        r.rid for r in accepted if svc.rid_has_change(session, review, r.rid)
    }
    queue = {
        "todo": [r for r in accepted if r.status is Status.CLOSED and r.rid not in changed_rids],
        "rework": [r for r in accepted if r.status is Status.CLOSED and r.rid in changed_rids],
        "awaiting": [r for r in accepted if r.status is Status.IMPLEMENTED],
        "done": [r for r in accepted if r.status is Status.VERIFIED],
    }
    eligible = queue["todo"] + queue["rework"]     # tickable in the save form
    return {
        "user": user, "review": review, "error": error,
        "content": latest.content if latest else "",
        "queue": queue, "eligible": eligible, "changed_rids": changed_rids,
    }


@web.get("/ui/reviews/{review_id}/closeout", response_class=HTMLResponse)
def closeout_page(review_id: str, request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    if review.status != ReviewStatus.CLOSEOUT.value:
        raise HTTPException(status_code=409, detail="the review is not in closeout")
    return templates.TemplateResponse(
        request, "closeout.html", _closeout_context(session, request, user, review)
    )


@web.post("/ui/reviews/{review_id}/closeout", response_class=HTMLResponse)
def closeout_save(
    review_id: str,
    request: Request,
    content: str = Form(...),
    rids: list[str] = Form(default=[]),
    session: Session = Depends(get_session),
):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    authz.forbid_ai_commit(user)
    try:
        svc.save_closeout_version(session, review, content, rid_ids=rids, by=user)
    except svc.PhaseError:
        raise HTTPException(status_code=409, detail="the review is not in closeout")
    except ValueError as exc:
        ctx = _closeout_context(session, request, user, review, error=str(exc))
        ctx["content"] = content            # keep the unsaved editor text
        return templates.TemplateResponse(request, "closeout.html", ctx, status_code=422)
    return RedirectResponse(f"/ui/reviews/{review_id}/closeout", 303)


@web.post("/ui/reviews/{review_id}/rids/{rid}/implement")
def mark_implemented(review_id: str, rid: str, request: Request, session: Session = Depends(get_session)):
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    authz.require_owner(session, review, user)
    authz.forbid_ai_commit(user)
    try:
        svc.implement(session, review, rid, by=user)
    except ValueError as exc:               # no linked change / wrong status
        raise HTTPException(status_code=422, detail=str(exc))
    return RedirectResponse(f"/ui/reviews/{review_id}/closeout", 303)


@web.get("/ui/reviews/{review_id}/implement")
def implement_redirect(review_id: str):
    """v2's implement page is superseded by the closeout workspace (v3)."""
    return RedirectResponse(f"/ui/reviews/{review_id}/closeout", 303)
```

  (`svc.rid_has_change(session, review, rid_id) -> bool` is a new one-liner
  public service wrapping `_post_baseline_changes` (`core.py:485-492`) — add it
  in this task, next to `link_change`.)

  `closeout.html` (evolved from `implement.html` — keep `editor-grid`,
  `#editor`/`#preview`, `marked` + `editor.js` includes and the unsaved-changes
  guard; drop the freeze-rule pre-check attributes, the owner is *supposed* to
  edit now):

```jinja
{% extends "base.html" %}
{% set nav_active = 'dashboard' %}
{% block title %}Closeout — {{ review.review_id_str }}{% endblock %}
{% block content %}
<p class="crumb"><a href="/ui/reviews/{{ review.review_id_str }}">← {{ review.review_id_str }}</a></p>
<h1>Closeout workspace</h1>
<p class="muted">Implement each accepted finding: edit the document, tick the RIDs the edit
resolves, save — then mark the finding implemented so its reviewer can verify it.</p>
{% if error %}<p class="error">{{ error }}</p>{% endif %}

<div class="closeout-grid">
  <aside class="closeout-queue">
    {% for group, label in [("rework", "Rework requested"), ("todo", "To implement"),
                            ("awaiting", "Awaiting verification"), ("done", "Verified")] %}
    <section class="cq-group cq-{{ group }}">
      <h2>{{ label }} <span class="badge">{{ queue[group]|length }}</span></h2>
      {% for r in queue[group] %}
      <div class="cq-item">
        <a href="/ui/reviews/{{ review.review_id_str }}/document?focus={{ r.rid }}">{{ r.rid }}</a>
        <span class="cmt">{{ (r.comment or '')|truncate(64) }}</span>
        {% if group == "rework" %}<span class="cq-reason">{{ (r.reply or '').split('[changes requested by')[-1]|truncate(96) }}</span>{% endif %}
        {% if group in ("todo", "rework") and r.rid in changed_rids %}
        <form method="post" action="/ui/reviews/{{ review.review_id_str }}/rids/{{ r.rid }}/implement" class="inline">
          <button class="secondary">Mark implemented</button>
        </form>
        {% endif %}
      </div>
      {% else %}<p class="muted">—</p>{% endfor %}
    </section>
    {% endfor %}
  </aside>

  <form method="post" action="/ui/reviews/{{ review.review_id_str }}/closeout" class="stack closeout-editor">
    <div class="editor-grid">
      <textarea id="editor" name="content" rows="24" spellcheck="false">{{ content }}</textarea>
      <div id="preview" class="preview"></div>
    </div>
    <fieldset class="rid-picker">
      <legend>This edit resolves</legend>
      {% for r in eligible %}
      <label class="chk"><input type="checkbox" name="rids" value="{{ r.rid }}"> {{ r.rid }} — {{ (r.comment or '')|truncate(56) }}</label>
      {% else %}<p class="muted">Nothing left to implement.</p>{% endfor %}
    </fieldset>
    <button class="primary">Save version &amp; link</button>
  </form>
</div>
<script src="/static/vendor/marked.min.js?v={{ asset_v }}"></script>
<script src="/static/editor.js?v={{ asset_v }}" defer></script>
{% endblock %}
```

  (`changed_rids` in the context is what lets the template show *Mark
  implemented* only when the service gate can pass.)
  CSS: `.closeout-grid { display:grid; grid-template-columns: 280px 1fr; gap:1rem; }`
  plus modest `.cq-group` styling consistent with `app.css` (match the metrics
  strip's badge/pill idiom; `cq-rework` accented with the existing `warn` amber).
  Retarget the dashboard button from step 01 to `/closeout`.
- [ ] **Step 4:** `python -m pytest -q` → PASS (update any v2 tests that hit
  `/implement` to the new flow: save no longer auto-advances; add an explicit
  mark-implemented POST where they relied on it).
- [ ] **Step 5:** `git commit -m "feat(web): closeout workspace — work queue, linked saves, explicit mark implemented"`

## Definition of Done

- [ ] Deliverables checked; suite green.
- [ ] Manual smoke: closeout review → workspace shows queue; save without ticks
  → error with text preserved; save with tick → version + link; Mark implemented
  appears only after a linked save; RID moves to *Awaiting verification*.

## Out of scope

Per-RID diff rendering & reviewer verification UI (03); finalize/downloads (04).
