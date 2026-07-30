# v3.1 Step 1 — Closeout moves into the document viewer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** the owner implements accepted findings **inside** the unified
document viewer — one wide column showing the latest version with a
`Render | Edit` toggle, and the side panel carrying the closeout work queue —
so the separate `/closeout` page disappears.

**Architecture:** no new page and no new endpoint. `_document_context` learns
the closeout payload the workspace used to build (`_closeout_context` folds
into it); `document.html` branches on `data.phase`; `document-viewer.js` grows
a closeout branch in `renderSheet` / `renderPanel` / `cardEl`. `POST
/ui/reviews/{id}/closeout` keeps its URL and its service call — only its caller
moves. `closeout.html` and `static/editor.js` are deleted.

**Tech stack:** FastAPI + Jinja, vanilla JS (no build step), vendored `marked`
+ `DOMPurify` (ADR 0003). Depends on v3 steps 01–03 (phases, closeout
services, `svc.rid_changes`).

## Global constraints

- Python 3.12+, PyYAML + Typer only — **no new runtime dependencies**.
- **No new vendored JS** (ADR 0003); no CDN at runtime.
- Every closeout mutation stays server-authoritative: the JS mirrors
  capabilities, it never grants them. `svc.save_closeout_version` and
  `svc.implement` keep their gates (≥1 accepted RID, real text change, ≥1
  linked change) untouched.
- Closure authority untouched: Verify / Request changes / Accept disposition
  belong to the RID's reviewer — or moderator / human global admin on their
  behalf — never the owner, never an AI.
- Conventional Commits; `python -m pytest -q` green at the end of every task.

## Deliverables

- [x] Closeout payload (`latest`, `canEditDoc`, per-RID `queue`/`hasChange`) in `_document_context`
- [x] `Render | Edit` toolbar + full-width editor in `document.html`, closeout only
- [x] Side panel renders the 4-group work queue with collapsed, expandable cards
- [x] RID checkboxes fused into the queue; `Save version & link (N)` wiring
- [x] `Mark implemented` inside the card via the detached-form `post()` helper
- [x] Comment popover gated to `in_review`
- [x] `closeout.html` + `editor.js` deleted; `GET /closeout` redirects to the document
- [x] CSS for the toolbar, editor and collapsed queue cards
- [x] Full suite green

---

### Task 1: the closeout payload in the viewer context

**Files:**
- Modify: `src/malus/web/router.py` (`_document_context` ~678–795, `_closeout_context` ~973–999)
- Test: `tests/web/test_closeout_in_document.py` (new)

**Interfaces produced** (consumed by Tasks 2–5 and by `document-viewer.js`):

```
data.latest        : str   — latest DocumentVersion content (closeout/finalized), else absent
data.latestOrdinal : int   — its ordinal
data.canEditDoc    : bool  — closeout AND (owner or global admin) AND not AI
data.rids[i].queue : "todo" | "rework" | "awaiting" | "done" | "noChange" | None
data.rids[i].hasChange : bool — a post-baseline RidChange already links this RID
```

Grouping rules, lifted verbatim from `_closeout_context` so behaviour does not
drift: `accepted + closed + not reworked → todo`; `accepted + closed +
reworked → rework`; `accepted + implemented → awaiting`; `accepted + verified
→ done`; `rejected | deferred → noChange`; anything else `None`. "Reworked"
means the reviewer sent it back — `"[changes requested by" in (reply or "")` —
**not** merely "a save already links it".

- [x] **Step 1: Write the failing test**

```python
"""Closeout payload in the unified viewer (v3.1 step 01 task 1): the work
queue the standalone workspace used to build now rides in ``#viewer-data``.
Seed helpers mirror ``tests/web/test_closeout_page.py``."""

from __future__ import annotations

import json

R = "SIN-SRS-R1"


def _payload(page_text: str) -> dict:
    marker = '<script type="application/json" id="viewer-data">'
    start = page_text.index(marker) + len(marker)
    end = page_text.index("</script>", start)
    return json.loads(page_text[start:end])


def _seed_closeout(mkuser, docs):
    """Owner + reviewer; one accepted RID, review flipped into closeout."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    owner.post(f"/reviews/{R}/harvest")
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "will fix", "resolution": ""},
    )
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    owner.post(f"/ui/reviews/{R}/start-closeout")
    return owner, f


def test_owner_gets_the_work_queue_in_the_viewer_payload(mkuser, docs):
    owner, _f = _seed_closeout(mkuser, docs)

    data = _payload(owner.get(f"/ui/reviews/{R}/document").text)

    assert data["canEditDoc"] is True
    assert data["latest"] == docs["baseline"]
    rid = next(r for r in data["rids"] if r["rid"] == "SIN-SRS-0001")
    assert rid["queue"] == "todo"
    assert rid["hasChange"] is False


def test_reviewer_sees_the_queue_but_may_not_edit(mkuser, docs):
    _owner, f = _seed_closeout(mkuser, docs)

    data = _payload(f.get(f"/ui/reviews/{R}/document").text)

    assert data["canEditDoc"] is False
    rid = next(r for r in data["rids"] if r["rid"] == "SIN-SRS-0001")
    assert rid["queue"] == "todo"


def test_in_review_carries_no_queue(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    owner.post(f"/reviews/{R}/harvest")

    data = _payload(owner.get(f"/ui/reviews/{R}/document").text)

    assert data["canEditDoc"] is False
    assert all(r["queue"] is None for r in data["rids"])
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/web/test_closeout_in_document.py -q`
Expected: FAIL — `KeyError: 'canEditDoc'`

- [x] **Step 3: Write minimal implementation**

In `src/malus/web/router.py`, inside `_document_context`, right after the
existing `changes` loop (the block that ends `r["changes"] = []`), add:

```python
    # v3.1 step 01: the closeout work queue rides in the viewer payload — the
    # side panel replaces the flat comment list with it (the standalone
    # workspace page is gone). Grouping lifted verbatim from the v3
    # _closeout_context so the buckets cannot drift apart.
    is_closeout = review.status == ReviewStatus.CLOSEOUT.value
    latest = VersionRepo(session).latest(review)
    for r in rids:
        group = None
        if r["disposition"] in (Disposition.REJECTED.value, Disposition.DEFERRED.value):
            group = "noChange"
        elif r["disposition"] == Disposition.ACCEPTED.value:
            reworked = "[changes requested by" in (r["reply"] or "")
            if r["status"] == Status.CLOSED.value:
                group = "rework" if reworked else "todo"
            elif r["status"] == Status.IMPLEMENTED.value:
                group = "awaiting"
            elif r["status"] == Status.VERIFIED.value:
                group = "done"
        r["queue"] = group if is_closeout else None
        r["hasChange"] = (
            is_closeout
            and r["disposition"] == Disposition.ACCEPTED.value
            and svc.rid_has_change(session, review, r["rid"])
        )
```

and extend the `data` dict with:

```python
        "latest": latest.content if latest else baseline.content,
        "latestOrdinal": latest.ordinal if latest else baseline.ordinal,
        "canEditDoc": is_closeout
        and (role == Role.OWNER.value or user.is_admin)
        and not user.is_ai,
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/web/test_closeout_in_document.py -q`
Expected: PASS (3 passed)

- [x] **Step 5: Commit**

```bash
git add src/malus/web/router.py tests/web/test_closeout_in_document.py
git commit -m "feat(web): closeout work queue rides in the viewer payload"
```

---

### Task 2: Render | Edit toolbar and the closeout editor

**Files:**
- Modify: `src/malus/web/templates/document.html`
- Test: `tests/web/test_closeout_in_document.py`

**Interfaces consumed:** `data.canEditDoc`, `data.latest` (Task 1).

The outer `<form id="rev-form">` already wraps both the sheet and the comments
panel, so in closeout it simply posts somewhere else. Exactly one element may
carry `name="content"`: the reviewer's hidden `#content-src`, or the closeout
`#doc-edit` textarea — never both.

- [x] **Step 1: Write the failing test**

```python
def test_closeout_form_posts_to_the_closeout_endpoint(mkuser, docs):
    owner, _f = _seed_closeout(mkuser, docs)

    html = owner.get(f"/ui/reviews/{R}/document").text

    assert f'action="/ui/reviews/{R}/closeout"' in html
    assert 'id="doc-edit"' in html
    assert 'id="doc-mode-edit"' in html          # the Render|Edit toggle
    assert 'id="content-src"' not in html        # the reviewer textarea is absent


def test_reviewer_in_closeout_gets_no_editor_and_no_popover(mkuser, docs):
    _owner, f = _seed_closeout(mkuser, docs)

    html = f.get(f"/ui/reviews/{R}/document").text

    assert 'id="doc-edit"' not in html
    assert 'id="cmt-pop"' not in html            # commenting is over in closeout
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/web/test_closeout_in_document.py -q`
Expected: FAIL — `assert 'action="/ui/reviews/SIN-SRS-R1/closeout"' in html`

- [x] **Step 3: Write minimal implementation**

In `src/malus/web/templates/document.html`, replace the form opening tag and
the sheet block:

```jinja
<form method="post" id="rev-form" hx-boost="false" data-review="{{ review.review_id_str }}"
      action="/ui/reviews/{{ review.review_id_str }}/{{ 'closeout' if data.canEditDoc else 'edit-copy' }}">
  {% if not data.canEditDoc %}<textarea id="content-src" name="content" hidden></textarea>{% endif %}
  {% if data.phase == 'closeout' %}
  <div class="doc-toolbar">
    <span class="doc-ver">v{{ data.latestOrdinal }}</span>
    <button type="button" id="doc-mode-render" class="secondary active">Render</button>
    {% if data.canEditDoc %}<button type="button" id="doc-mode-edit" class="secondary">Edit</button>{% endif %}
  </div>
  {% endif %}
  <div class="workbench">
    <div id="sheet" class="a4-sheet doc-sheet" aria-label="Rendered document"></div>
    {% if data.canEditDoc %}
    <textarea id="doc-edit" name="content" class="doc-edit" spellcheck="false" hidden>{{ data.latest }}</textarea>
    {% endif %}
    <aside class="comments-panel">
```

Keep the rest of the `workbench`/`aside` block as it is. Then gate the
reviewer action bar and the popover on the phase — change both
`{% if data.isReviewer and not data.mySubmitted %}` guards (the `rev-actions`
block and the `cmt-pop` block) to:

```jinja
{% if data.isReviewer and not data.mySubmitted and data.phase == 'in_review' %}
```

and add the save bar for the owner:

```jinja
{% if data.canEditDoc %}
<div class="rev-actions">
  <button type="submit" class="primary" id="closeout-save" disabled>
    Save version &amp; link (<span id="rid-count">0</span>)</button>
</div>
{% endif %}
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/web/test_closeout_in_document.py -q`
Expected: PASS (5 passed)

- [x] **Step 5: Commit**

```bash
git add src/malus/web/templates/document.html tests/web/test_closeout_in_document.py
git commit -m "feat(web): Render|Edit toolbar and closeout editor in the document viewer"
```

---

### Task 3: the sheet renders the latest version in closeout

**Files:**
- Modify: `src/malus/web/static/document-viewer.js` (`renderSheet` ~157–188, `refresh` ~742)
- Test: manual — see the verification block below (no JS test harness in this repo; every automated assertion lives server-side)

Comment anchors are baseline offsets; the latest version has moved past them,
so closeout renders **no markers**. The per-comment `Changes` diff in the card
is the anchor from here on. The render still goes through `marked` **and**
`DOMPurify` — the deleted `editor.js` preview called `marked` alone, which was
a standing self-XSS on the owner.

- [x] **Step 1: Write the implementation**

In `src/malus/web/static/document-viewer.js`, at the top of `renderSheet`:

```javascript
  function renderSheet(its) {
    if (data.phase === "closeout") {
      // closeout: the sheet shows the LATEST version, unmarked — comment
      // offsets belong to the baseline and no longer line up. marked +
      // DOMPurify, same pipeline as the review-phase sheet.
      var src = editEl ? editEl.value : data.latest;
      var out = window.marked ? window.marked.parse(src) : esc(src);
      sheet.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(out) : out;
      return;
    }
    var outSrc = "", prev = 0;
```

and declare the editor handle next to the other element lookups near the top
of the IIFE (beside `sheet`, `list`, `legendEl`):

```javascript
  var editEl = document.getElementById("doc-edit");
```

- [x] **Step 2: Wire the Render | Edit toggle**

Append to the init section, just before `parseCopy();`:

```javascript
  /* ---------------- closeout: Render | Edit ----------------------------- */
  var modeRender = document.getElementById("doc-mode-render");
  var modeEdit = document.getElementById("doc-mode-edit");
  function setMode(edit) {
    if (!editEl) return;
    editEl.hidden = !edit;
    sheet.hidden = edit;
    if (modeEdit) modeEdit.classList.toggle("active", edit);
    if (modeRender) modeRender.classList.toggle("active", !edit);
    if (!edit) renderSheet(currentItems);   // re-render from the edited text
  }
  if (modeRender) modeRender.addEventListener("click", function () { setMode(false); });
  if (modeEdit) modeEdit.addEventListener("click", function () { setMode(true); });
```

- [x] **Step 3: Verify by hand**

Run the app, open a review in closeout as the owner:

```bash
.venv/bin/malus serve --host 127.0.0.1 --port 8000
```

Expected: the document column shows the latest version rendered; `Edit` swaps
in the textarea at full width; `Render` swaps back and reflects the edits;
no comment markers appear in the text.

- [x] **Step 4: Run the suite**

Run: `python -m pytest -q`
Expected: PASS, no regressions

- [x] **Step 5: Commit**

```bash
git add src/malus/web/static/document-viewer.js
git commit -m "feat(web): closeout sheet renders the latest version, sanitized"
```

---

### Task 4: the side panel becomes the work queue

**Files:**
- Modify: `src/malus/web/static/document-viewer.js` (`renderPanel` ~557–562, `cardEl` ~234–499)
- Test: `tests/web/test_closeout_in_document.py` (payload-level assertions only)

Four groups in this order — `Rework requested`, `To implement`, `Awaiting
verification`, `Verified` — plus a collapsed `<details>` group `Closed — no
change` for the `noChange` bucket. Cards render **collapsed** in closeout:
head visible, everything else behind the disclosure. `?focus=RID` expands its
card (the existing `setFocus` already opens the history `<details>`; extend it
to clear `collapsed`).

- [x] **Step 1: Write the implementation — grouped panel**

Replace `renderPanel`:

```javascript
  var QUEUE_GROUPS = [
    ["rework", "Rework requested"],
    ["todo", "To implement"],
    ["awaiting", "Awaiting verification"],
    ["done", "Verified"],
  ];
  function renderPanel(its) {
    list.innerHTML = "";
    countEl.textContent = String(its.length);
    emptyEl.hidden = its.length > 0;
    if (data.phase !== "closeout") {
      its.forEach(function (it) { list.appendChild(cardEl(it)); });
      return;
    }
    QUEUE_GROUPS.forEach(function (g) {
      var members = its.filter(function (it) { return it.rid && it.rid.queue === g[0]; });
      var sec = document.createElement("section");
      sec.className = "cq-group cq-" + g[0];
      sec.innerHTML = '<h2>' + esc(g[1]) + ' <span class="badge">' + members.length + "</span></h2>";
      members.forEach(function (it) { sec.appendChild(cardEl(it)); });
      if (!members.length) sec.innerHTML += '<p class="muted">—</p>';
      list.appendChild(sec);
    });
    var closed = its.filter(function (it) { return it.rid && it.rid.queue === "noChange"; });
    if (closed.length) {
      var det = document.createElement("details");
      det.className = "cq-group cq-nochange";
      det.innerHTML = "<summary>Closed — no change (" + closed.length + ")</summary>";
      closed.forEach(function (it) { det.appendChild(cardEl(it)); });
      list.appendChild(det);
    }
  }
```

- [x] **Step 2: Write the implementation — collapsed cards**

In `cardEl`, immediately after `card.setAttribute("data-key", it.key);`:

```javascript
    if (phase === "closeout") {
      // collapsed by default: the queue must stay scannable; the head toggles
      card.classList.add("collapsed");
      card.addEventListener("click", function (ev) {
        if (ev.target.closest(".cp-body, .cp-actions, .cp-changes, button, input, textarea, select, label, a, summary")) return;
        card.classList.toggle("collapsed");
      });
    }
```

and in `setFocus`, inside the existing `if (on) { … }` branch, add
`el.classList.remove("collapsed");` next to the history `open = true` line.

- [x] **Step 3: Run the suite**

Run: `python -m pytest -q`
Expected: PASS, no regressions

- [x] **Step 4: Verify by hand**

Open the document as the owner in closeout: the panel shows the four groups
with counts, cards collapsed; clicking a head expands one; a rejected finding
sits inside the collapsed `Closed — no change` disclosure; opening
`?focus=SIN-SRS-0001` lands with that card expanded.

- [x] **Step 5: Commit**

```bash
git add src/malus/web/static/document-viewer.js
git commit -m "feat(web): side panel renders the closeout queue as collapsed cards"
```

---

### Task 5: RID checkboxes, the save counter, and Mark implemented

**Files:**
- Modify: `src/malus/web/static/document-viewer.js` (`cardEl`)
- Modify: `src/malus/web/router.py` (`mark_implemented` ~1042, redirect target)
- Test: `tests/web/test_closeout_in_document.py`

Nested forms are illegal in HTML and the panel lives inside `#rev-form`, so
`Mark implemented` submits through the existing detached-form `post()` helper
— the same mechanism Verify / Accept / Reopen already use.

- [x] **Step 1: Write the failing test**

```python
def test_saving_from_the_document_links_the_ticked_rid(mkuser, docs):
    owner, _f = _seed_closeout(mkuser, docs)
    edited = docs["baseline"].replace("shall", "must", 1)

    r = owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": edited, "rids": ["SIN-SRS-0001"]},
        follow_redirects=False,
    )

    assert r.status_code == 303
    data = _payload(owner.get(f"/ui/reviews/{R}/document").text)
    rid = next(x for x in data["rids"] if x["rid"] == "SIN-SRS-0001")
    assert rid["hasChange"] is True
    assert data["latest"] == edited


def test_mark_implemented_returns_to_the_document_focused(mkuser, docs):
    owner, _f = _seed_closeout(mkuser, docs)
    owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": docs["baseline"].replace("shall", "must", 1), "rids": ["SIN-SRS-0001"]},
    )

    r = owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/implement",
        data={"resolution": "reworded"},
        follow_redirects=False,
    )

    assert r.status_code == 303
    assert r.headers["location"] == f"/ui/reviews/{R}/document?focus=SIN-SRS-0001"
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/web/test_closeout_in_document.py -q`
Expected: FAIL — the redirect still points at `/ui/reviews/SIN-SRS-R1/closeout`

- [x] **Step 3: Write minimal implementation**

In `src/malus/web/router.py`, `mark_implemented`, change the final line to:

```python
    return RedirectResponse(f"/ui/reviews/{review_id}/document?focus={rid}", 303)
```

In `cardEl`, before the `actions` block is appended, add the closeout owner
controls:

```javascript
    if (r && data.canEditDoc && (r.queue === "todo" || r.queue === "rework")) {
      // the edit↔RID picker IS the queue: tick the findings this save resolves
      var pick = document.createElement("label");
      pick.className = "cq-pick";
      var box = document.createElement("input");
      box.type = "checkbox";
      box.name = "rids";
      box.value = r.rid;
      box.addEventListener("change", syncSaveButton);
      pick.appendChild(box);
      pick.appendChild(document.createTextNode(" this edit resolves it"));
      card.appendChild(pick);

      if (r.hasChange) {  // implement is gated server-side on a linked change
        var res = document.createElement("input");
        res.type = "text";
        res.className = "cq-resolution-input";
        res.placeholder = "what was done (resolution)";
        var mark = document.createElement("button");
        mark.type = "button";
        mark.className = "secondary cp-implement";
        mark.textContent = "Mark implemented";
        mark.addEventListener("click", function (ev) {
          ev.stopPropagation();
          post(base + "/rids/" + encodeURIComponent(r.rid) + "/implement",
            { resolution: res.value });
        });
        actions.appendChild(res);
        actions.appendChild(mark);
      }
    }
```

and add the counter helper next to `renderPanel`:

```javascript
  function syncSaveButton() {
    var btn = document.getElementById("closeout-save");
    if (!btn || !editEl) return;
    var n = list.querySelectorAll('input[name="rids"]:checked').length;
    var counter = document.getElementById("rid-count");
    if (counter) counter.textContent = String(n);
    // the service rejects both cases anyway — this only saves the round-trip
    btn.disabled = n === 0 || editEl.value === data.latest;
  }
```

Call `syncSaveButton()` at the end of `refresh`, and bind
`editEl.addEventListener("input", syncSaveButton)` in the toggle block from
Task 3.

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/web/test_closeout_in_document.py -q`
Expected: PASS (7 passed)

- [x] **Step 5: Commit**

```bash
git add src/malus/web/router.py src/malus/web/static/document-viewer.js tests/web/test_closeout_in_document.py
git commit -m "feat(web): queue checkboxes drive the closeout save; implement from the card"
```

---

### Task 6: retire the standalone workspace

**Files:**
- Delete: `src/malus/web/templates/closeout.html`, `src/malus/web/static/editor.js`
- Modify: `src/malus/web/router.py` (`_closeout_context` ~973, `closeout_page` ~1002, `closeout_save` ~1016)
- Test: `tests/web/test_closeout_page.py` (rewrite the GET cases)

`GET /closeout` keeps answering — as a 303 to the document, the same courtesy
`GET /implement` got in v3. `POST /closeout` stays; on a `ValueError` it now
re-renders **document.html** with the unsaved text, which needs a
`content_override` on `_document_context` mirroring the existing
`my_copy_override`.

- [x] **Step 1: Write the failing test**

Replace the GET tests in `tests/web/test_closeout_page.py` with:

```python
def test_closeout_get_redirects_to_the_document(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)

    r = owner.get(f"/ui/reviews/{R}/closeout", follow_redirects=False)

    assert r.status_code == 303
    assert r.headers["location"] == f"/ui/reviews/{R}/document"


def test_rejected_save_re_renders_the_document_with_the_unsaved_text(mkuser, docs):
    owner, f, mod = _seed_answered(mkuser, docs)
    _to_closeout(owner, f, mod)
    edited = docs["baseline"].replace("shall", "must", 1)

    r = owner.post(f"/ui/reviews/{R}/closeout", data={"content": edited, "rids": []})

    assert r.status_code == 422
    assert "at least one accepted RID" in r.text
    assert 'id="doc-edit"' in r.text          # still the document page
    assert "must" in r.text                    # the unsaved edit survived
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/web/test_closeout_page.py -q`
Expected: FAIL — GET returns 200 (the workspace page), not 303

- [x] **Step 3: Write minimal implementation**

Delete `src/malus/web/templates/closeout.html`, `src/malus/web/static/editor.js`
and the whole `_closeout_context` function. Replace the two routes:

```python
@web.get("/ui/reviews/{review_id}/closeout")
def closeout_redirect(review_id: str):
    """v3's standalone workspace is folded into the viewer (v3.1 step 01)."""
    return RedirectResponse(f"/ui/reviews/{review_id}/document", 303)
```

and, in `closeout_save`, swap the error branch for:

```python
    except ValueError as exc:
        ctx = _document_context(
            session, request, user, review, error=str(exc), content_override=content
        )
        return templates.TemplateResponse(request, "document.html", ctx, status_code=422)
    return RedirectResponse(f"/ui/reviews/{review_id}/document", 303)
```

Add the parameter to `_document_context` (`content_override: Optional[str] = None`)
and use it where `latest` feeds the payload:

```python
        "latest": content_override
        if content_override is not None
        else (latest.content if latest else baseline.content),
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/web/test_closeout_page.py tests/web/test_closeout_in_document.py -q`
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add -A src/malus/web tests/web
git commit -m "refactor(web): retire the standalone closeout workspace"
```

---

### Task 7: CSS for the toolbar, the editor and the collapsed cards

**Files:**
- Modify: `src/malus/web/static/app.css` (the `.editor-grid` / `closeout workspace` blocks at lines 221–245 become the new closeout styles; `.comments-panel` block at 277)
- Test: `tests/web/test_assets.py` (asset wiring only)

The app is light-only and token-driven; reuse `var(--card)`, `var(--line)`,
`var(--muted)`, `var(--mono)`, `var(--radius-sm)`, `var(--shadow)`. Keep the
`.cq-group` / `.cq-rework` styling that already exists — it now dresses the
panel groups instead of the deleted page.

- [x] **Step 1: Write the implementation**

Replace the `.editor-grid` / `.preview` / `.rid-picker` / `.chk` rules and the
`.closeout-grid` rule (they belonged to the deleted page) with:

```css
/* ------------------------------------------------ closeout in the viewer -- */
.doc-toolbar { display: flex; align-items: center; gap: .4rem; margin-bottom: .6rem; }
.doc-toolbar .doc-ver { font-family: var(--mono); font-size: .78rem; color: var(--muted); margin-right: .3rem; }
.doc-toolbar button.active { box-shadow: inset 0 0 0 2px var(--teal); }
.doc-edit { width: 100%; min-height: 1120px; font-family: var(--mono); font-size: .85rem;
  padding: 60px 72px; border: 1px solid var(--line); border-radius: 6px; background: #fff; }
.cp-card.collapsed .cp-body { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.cp-card.collapsed .cp-detail,
.cp-card.collapsed .cp-records,
.cp-card.collapsed .cp-history,
.cp-card.collapsed .cp-changes,
.cp-card.collapsed .cp-actions,
.cp-card.collapsed .cp-note-label,
.cp-card.collapsed .cq-pick { display: none; }
.cq-pick { display: block; font-size: .8rem; color: var(--muted); margin-top: .4rem; }
.cq-resolution-input { font-size: .8rem; padding: .2rem .4rem; flex: 1; min-width: 0; }
.cq-nochange > summary { font-size: .82rem; font-weight: 600; cursor: pointer; }
@media (max-width: 900px) { .doc-edit { padding: 24px; min-height: 40rem; } }
```

- [x] **Step 2: Run the suite**

Run: `python -m pytest -q`
Expected: PASS

- [x] **Step 3: Verify by hand**

Owner in closeout: toolbar sits above the document, the active mode is
outlined, `Edit` gives a full-width monospace editor at the sheet's width, the
queue cards are two lines tall until expanded.

- [x] **Step 4: Commit**

```bash
git add src/malus/web/static/app.css
git commit -m "style(web): closeout toolbar, editor and collapsed queue cards"
```

---

## Definition of Done

- [x] All seven tasks committed, `python -m pytest -q` green
- [x] `/ui/reviews/{id}/closeout` GET redirects; POST still saves, and rejects
      re-render the document with the unsaved text
- [x] `closeout.html` and `editor.js` no longer exist; nothing references them
      (`grep -rn "editor.js\|closeout.html" src/`) apart from historical plan files
- [x] An owner in closeout can: read the latest version, switch to Edit, tick
      one or more findings, save, then mark one implemented — without leaving
      the document page
- [x] A reviewer in closeout sees the same queue, their own cards carry Verify
      and Request changes under the diff, and they can neither edit the
      document nor add a comment
- [x] Closeout preview HTML passes through DOMPurify (the v3 self-XSS minor is
      closed)
- [x] Deviations recorded under a `## Deviations` heading in this file

## Deviations

Agreed with Alberto Boffi before implementation started (session of 2026-07-30);
each is recorded with the reason.

1. **Tests outside `test_closeout_page.py` had to be retargeted.** The step file
   only anticipated rewriting that file's GET cases, but six pre-existing tests
   asserted the old contract, and "green after every task" is unreachable
   without them. All were retargeted, none deleted:
   - `test_closeout_page.py`: the save's redirect (`/closeout` → `/document`),
     the Mark-implemented redirect (`→ /document?focus={rid}`), and the two
     assertions that read the queue out of the deleted page's HTML — they now
     read `queue` / `hasChange` from the `#viewer-data` payload. The GET 403 and
     GET 409 cases were dropped: the route is an unconditional redirect now (the
     same shape `GET /implement` has had since v3), so it has no role or phase
     to refuse on.
   - `test_lifecycle_v3_web.py` + `test_editor.py`: both asserted
     `GET /closeout` → 409 outside closeout. That phase gate now lives only on
     the save, so both were moved onto `POST /closeout` → 409, and
     `test_implement_page_allowed_in_closeout` became
     `test_closeout_get_redirects_into_the_viewer`. Net effect: the web-level
     phase gate is still covered — on the endpoint that actually enforces it.
2. **CSS: the dead `.closeout-queue` / `.cq-item*` rules were removed too**, not
   just the ones the step file names — they styled only the deleted page.
   `.cq-group` / `.cq-rework` were kept as instructed, plus one addition:
   `.cq-group { margin-bottom: .8rem }`, because the group spacing used to come
   from the deleted `.closeout-queue { display: flex; gap: .8rem }` wrapper.
3. **`setFocus` also opens the enclosing `<details>`.** The task-4 snippet only
   cleared `collapsed`, which left a focused card invisible inside the collapsed
   `Closed — no change` group — so `?focus=<a rejected RID>` looked like a no-op.
   Two lines added: `el.closest("details.cq-group").open = true`.
4. **One test added beyond the step file** —
   `test_unsubmitted_reviewer_cannot_comment_in_closeout`. The step's
   `test_reviewer_in_closeout_gets_no_editor_and_no_popover` passes vacuously:
   its reviewer has already submitted, so the popover was hidden by the old
   `mySubmitted` guard, not by the new phase guard. The added test seeds a
   second reviewer whose copy is still a draft — the exact defect the design
   names — and fails without the `phase == 'in_review'` gate.
5. **Naming only:** in `renderSheet`'s closeout branch the locals are `csrc` /
   `cout` rather than the snippet's `src` / `out`, to avoid shadowing the
   module-level `src` (the reviewer's `#content-src` handle).
6. **Environment:** the suite was run as `.venv/bin/python -m pytest`
   (`python` is not on PATH on this machine). 468 tests green.

Observations for the next steps, not changed here:

- `GET /implement` still redirects to `/closeout`, which now redirects again to
  `/document` — a harmless 303 chain, and the existing test documents it. Worth
  collapsing whenever that route is next touched.
- In closeout a reviewer sees a toolbar holding the version chip and a lone,
  already-active `Render` button (the `Edit` button is correctly owner-only).
  It is what the design specifies; if the bare button reads as noise, gate the
  whole `.doc-toolbar` on `canEditDoc` and keep the version chip.
- Screenshots could not be captured in this environment (the preview renderer
  produced no frames). The manual verification blocks were satisfied against a
  seeded review on a live server — computed geometry, styles, the accessibility
  tree and real clicks — but no image was recorded.

## Out of scope

- The `Terminate review` button and the admin reopen — step 02.
- Diff view modes and the duplicate dashboard button — step 03.
- Downloads — step 04.
- Removing `create_all` from the boot path — step 05.
- Any change to the RID state machine, the phase gates, or closure authority.
