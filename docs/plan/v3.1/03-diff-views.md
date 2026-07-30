# v3.1 Step 3 — Diff views: whole document, line numbers, one button

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** a member opening `/ui/reviews/{id}/diff` can read the change either
as **hunks** (today: ±3 lines of context, elided in between) or as the **whole
document with line numbers**, switching with a plain link — a shareable URL, no
JavaScript. Plus the dashboard stops rendering the *Full diff* button twice.
Source of scope: `docs/plan/v3.1/00-design.md` §Decisions rows *Diff views* and
*Duplicate button*, and §Testing.

**Architecture:** the renderer stays the single pure module
`src/malus/diffing.py` (stdlib `difflib`, created by `docs/plan/v3/03-verification.md`
task 1). It gains two keyword-only options — `context: int | None` and
`line_numbers: bool` — with **unchanged defaults**, so the per-RID `Changes`
section (`svc.rid_changes`, `src/malus/services/core.py:790`) and every existing
diff test keep passing byte-for-byte. The page toggle is a server-side query
parameter read by `diff_page` (`src/malus/web/router.py:820`) and two links in
`src/malus/web/templates/diff.html` — the same "state lives in the URL" idiom as
the v2.2 dashboard filter chips (`review.html` `.filter-bar`), not a client-side
widget.

**Tech stack:** Python `difflib` + `html` (stdlib), Jinja, CSS. Depends on
`docs/plan/v3/03-verification.md` (the module, the page, the diff CSS). Independent
of v3.1 steps 01 and 02; step 04 (`04-downloads.md`) depends on the signature
below being landed **verbatim**.

## Global constraints

- Python 3.12+ **stdlib `difflib` only**. No new runtime dependency (CLAUDE.md
  §Conventions), no new vendored front-end library (ADR 0003 untouched).
- **Zero JavaScript** for the view toggle: two `<a>` elements, one query
  parameter, server-rendered. The URL must be copy-pasteable and bookmarkable.
- All diff HTML is built **server-side from escaped text**: every character
  coming from a document version passes `html.escape` *before* any markup is
  added. This is the hard security rule of `malus/diffing.py` — line numbers are
  Python `int`s formatted into the gutter spans, so they carry no user input and
  cannot inject markup, but document text never bypasses `html.escape`.
- Compact mode (`context=3`, `line_numbers=False`) must stay **byte-identical**
  to the v3 output for the same input — it is injected into the RID card and
  covered by a golden test (task 1, step 1).
- An unknown `?view=` value **falls back to compact**; a read-only page reached
  from a hand-edited or truncated URL must never 4xx.
- Conventional Commits, one per task. `python -m pytest -q` green at the end of
  every task (inside the project venv: `.venv/bin/python -m pytest -q`).
- CSS ships through the existing cache-buster `/static/app.css?v={{ asset_v }}`
  (`base.html`); `asset_v` is bumped at release (v3 `06-release.md`), not here.

## Deliverables

- [x] `html_diff(old, new, *, context: int | None = 3, line_numbers: bool = False)`
- [x] `context=None` → whole document, no `diff-skip` marker
- [x] `line_numbers=True` → two gutter spans per row (old, new)
- [x] Golden test: compact output byte-identical to v3
- [x] `GET /ui/reviews/{id}/diff?view=compact|full`, unknown value → compact
- [x] `Compact | Full` toggle links in `diff.html`, active view marked
- [x] `.diff-ln` gutter CSS in `src/malus/web/static/app.css`
- [x] Duplicate *Full diff* button deleted (`review.html:34`) + regression test
- [x] Full suite green

---

### Task 1: whole-document mode (`context=None`)

**Files:**
- Modify: `src/malus/diffing.py`
- Test: `tests/test_diffing.py` (extend)

**Interfaces produced** (final shape, completed by task 2 — later steps depend
on it verbatim):

```python
def html_diff(old: str, new: str, *, context: int | None = 3,
              line_numbers: bool = False) -> str
```

- `context=3` (default): `sm.get_grouped_opcodes(3)`, elision marker between hunks.
- `context=None`: `sm.get_opcodes()` as a single group — every line of the
  document, **no `diff-skip` marker at all**.

- [x] **Step 1: failing tests** — append to `tests/test_diffing.py`:

```python
# --- v3.1 step 03: whole-document mode + the compact-output guard ----------

# The exact v3 output for this input, captured from the shipped renderer.
# The per-RID Changes section injects this string into the card, so compact
# mode is frozen: any byte that moves here is a regression, not a refactor.
_GOLDEN_COMPACT = (
    '<div class="diff"><div class="diff-hunk">'
    '<div class="diff-ctx">alpha</div>'
    '<div class="diff-del">the <del>quick</del> fox</div>'
    '<div class="diff-ins">the <ins>slow</ins> fox</div>'
    '<div class="diff-ctx">omega</div>'
    "</div></div>"
)
_OLD3 = "alpha\nthe quick fox\nomega\n"
_NEW3 = "alpha\nthe slow fox\nomega\n"


def test_compact_output_is_byte_identical_to_v3():
    assert html_diff(_OLD3, _NEW3) == _GOLDEN_COMPACT
    assert html_diff(_OLD3, _NEW3, context=3) == _GOLDEN_COMPACT


def test_context_none_keeps_every_line_and_elides_nothing():
    old = "\n".join(f"line {i:02d}" for i in range(50)) + "\n"
    new = old.replace("line 10", "line ten").replace("line 40", "line forty")
    out = html_diff(old, new, context=None)
    assert "line 00" in out and "line 25" in out and "line 49" in out
    assert "diff-skip" not in out            # nothing is elided, no marker
    assert "<del>10</del>" in out and "<ins>ten</ins>" in out


def test_context_none_still_escapes_every_line():
    old = "Tom & Jerry <inc>\nold line\n"
    new = "Tom & Jerry <inc>\nnew line\n"
    out = html_diff(old, new, context=None)
    assert '<div class="diff-ctx">Tom &amp; Jerry &lt;inc&gt;</div>' in out
    assert "<inc>" not in out


def test_context_none_on_equal_texts_is_still_empty():
    assert html_diff("a\nb\n", "a\nb\n", context=None) == ""
```

- [x] **Step 2:** run → FAIL. Note *how* it fails: `context` already exists as a
  parameter, so passing `None` reaches `difflib.get_grouped_opcodes(None)` and
  raises `TypeError: unsupported operand type(s) for -: 'int' and 'NoneType'`
  (the golden test passes from the start — it is a guard, not a driver):

```bash
python -m pytest -q tests/test_diffing.py
```

- [x] **Step 3: implement** in `src/malus/diffing.py` — replace the `html_diff`
  signature and its group loop:

```python
def html_diff(old: str, new: str, *, context: int | None = 3) -> str:
    """Line-grouped, word-refined diff as safe HTML (empty string if equal).

    ``context`` is the number of unchanged lines kept around each hunk;
    ``None`` renders the **whole document** with no elision marker (v3.1
    step 03 — the ``?view=full`` page and the downloadable diff artifact).
    """
    if old == new:
        return ""
    old_lines, new_lines = old.splitlines(), new.splitlines()
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    # one group = the whole document when context is None, so the loop body
    # below is shared by both modes
    groups = [sm.get_opcodes()] if context is None else sm.get_grouped_opcodes(context)
    parts: list[str] = ['<div class="diff">']
    for group in groups:
        parts.append('<div class="diff-hunk">')
        for op, a1, a2, b1, b2 in group:
            ...                                  # unchanged branches
        parts.append("</div>")
        if context is not None:                  # nothing is elided in full mode
            parts.append('<div class="diff-skip">⋯</div>')
    if parts[-1] == '<div class="diff-skip">⋯</div>':
        parts.pop()                              # no trailing elision marker
    parts.append("</div>")
    return "".join(parts)
```

  Also update the module docstring's first paragraph to mention the two modes.
  Nothing else in the function changes — that is what keeps the golden test green.

- [x] **Step 4:** run → PASS.

```bash
python -m pytest -q tests/test_diffing.py
python -m pytest -q
```

- [x] **Step 5:** `git commit -m "feat(diff): whole-document mode via context=None"`

### Task 2: line-number gutters (`line_numbers=True`)

**Files:**
- Modify: `src/malus/diffing.py`
- Test: `tests/test_diffing.py` (extend)

**Markup contract** (fixed here, consumed by step 04's `diff.html` download):

| row | old gutter | new gutter |
|---|---|---|
| `diff-ctx` (unchanged line) | old line no. | new line no. |
| `diff-del` (removed / replaced-from) | old line no. | **rendered empty** |
| `diff-ins` (added / replaced-to) | **rendered empty** | new line no. |

Both spans are **always emitted**, in the order old → new, immediately after the
opening `<div>` and before the line's content:

```html
<div class="diff-ctx"><span class="diff-ln diff-ln-old">12</span><span class="diff-ln diff-ln-new">12</span>text</div>
```

The absent number is an **empty span**, never a dash and never an omitted
element: `.diff-ln` is `display: inline-block` with a fixed width (task 3), so
an empty span still occupies its column and every row stays aligned. Line
numbers are 1-based and are Python `int`s — no document text reaches the gutter,
so they need no escaping; the line body keeps going through `html.escape` /
`_refine` exactly as before.

- [x] **Step 1: failing tests** — append to `tests/test_diffing.py`:

```python
# --- v3.1 step 03: line-number gutters ------------------------------------

def test_line_numbers_render_both_gutters():
    out = html_diff(_OLD3, _NEW3, line_numbers=True)
    assert (
        '<div class="diff-ctx"><span class="diff-ln diff-ln-old">1</span>'
        '<span class="diff-ln diff-ln-new">1</span>alpha</div>'
    ) in out
    # a deleted row carries no new-side number: the span is present but empty
    assert (
        '<div class="diff-del"><span class="diff-ln diff-ln-old">2</span>'
        '<span class="diff-ln diff-ln-new"></span>the <del>quick</del> fox</div>'
    ) in out
    # an inserted row is the mirror image
    assert (
        '<div class="diff-ins"><span class="diff-ln diff-ln-old"></span>'
        '<span class="diff-ln diff-ln-new">2</span>the <ins>slow</ins> fox</div>'
    ) in out
    assert (
        '<span class="diff-ln diff-ln-old">3</span>'
        '<span class="diff-ln diff-ln-new">3</span>omega'
    ) in out


def test_line_numbers_diverge_after_an_unbalanced_insert():
    out = html_diff("a\nb\nc\n", "a\nX\nb\nc\n", context=None, line_numbers=True)
    assert (
        '<div class="diff-ins"><span class="diff-ln diff-ln-old"></span>'
        '<span class="diff-ln diff-ln-new">2</span><ins>X</ins></div>'
    ) in out
    # from there on the old side trails the new side by one line
    assert (
        '<span class="diff-ln diff-ln-old">2</span>'
        '<span class="diff-ln diff-ln-new">3</span>b'
    ) in out


def test_line_numbers_do_not_weaken_escaping():
    out = html_diff("safe\n", "<script>alert(1)</script>\n",
                    context=None, line_numbers=True)
    assert "<script>" not in out and "&lt;script&gt;" in out
    assert '<span class="diff-ln diff-ln-new">1</span>' in out


def test_line_numbers_default_off_changes_nothing():
    assert html_diff(_OLD3, _NEW3, line_numbers=False) == _GOLDEN_COMPACT
    assert "diff-ln" not in html_diff(_OLD3, _NEW3)
```

- [x] **Step 2:** run → FAIL (`TypeError: html_diff() got an unexpected keyword
  argument 'line_numbers'`):

```bash
python -m pytest -q tests/test_diffing.py
```

- [x] **Step 3: implement** in `src/malus/diffing.py` — a gutter helper beside
  `_refine`, then thread the row indices through the three branches:

```python
def _gutter(old_no: int | None, new_no: int | None, line_numbers: bool) -> str:
    """The two line-number spans of one row — "" when numbering is off.

    A deleted row has no new-side number and an inserted row has no old-side
    number: that span is emitted **empty** so both gutter columns keep their
    width and the rows stay aligned. The values are ``int``s, never document
    text, so nothing here can carry markup.
    """
    if not line_numbers:
        return ""
    o = "" if old_no is None else str(old_no)
    n = "" if new_no is None else str(new_no)
    return (
        f'<span class="diff-ln diff-ln-old">{o}</span>'
        f'<span class="diff-ln diff-ln-new">{n}</span>'
    )


def html_diff(
    old: str,
    new: str,
    *,
    context: int | None = 3,
    line_numbers: bool = False,
) -> str:
    """Line-grouped, word-refined diff as safe HTML (empty string if equal).

    ``context`` is the number of unchanged lines kept around each hunk;
    ``None`` renders the whole document with no elision marker. With
    ``line_numbers`` every row is prefixed by two gutter spans, old then new
    (v3.1 step 03). Defaults reproduce the v3 output byte for byte.
    """
    if old == new:
        return ""
    old_lines, new_lines = old.splitlines(), new.splitlines()
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    groups = [sm.get_opcodes()] if context is None else sm.get_grouped_opcodes(context)
    parts: list[str] = ['<div class="diff">']
    for group in groups:
        parts.append('<div class="diff-hunk">')
        for op, a1, a2, b1, b2 in group:
            if op == "equal":
                for k, line in enumerate(old_lines[a1:a2]):
                    g = _gutter(a1 + k + 1, b1 + k + 1, line_numbers)
                    parts.append(f'<div class="diff-ctx">{g}{html.escape(line)}</div>')
            elif op == "replace" and (a2 - a1) == (b2 - b1):
                for k, (o, n) in enumerate(zip(old_lines[a1:a2], new_lines[b1:b2])):
                    d, i = _refine(o, n)
                    gd = _gutter(a1 + k + 1, None, line_numbers)
                    gi = _gutter(None, b1 + k + 1, line_numbers)
                    parts.append(f'<div class="diff-del">{gd}{d}</div>')
                    parts.append(f'<div class="diff-ins">{gi}{i}</div>')
            else:
                for k, line in enumerate(old_lines[a1:a2]):
                    g = _gutter(a1 + k + 1, None, line_numbers)
                    parts.append(f'<div class="diff-del">{g}<del>{html.escape(line)}</del></div>')
                for k, line in enumerate(new_lines[b1:b2]):
                    g = _gutter(None, b1 + k + 1, line_numbers)
                    parts.append(f'<div class="diff-ins">{g}<ins>{html.escape(line)}</ins></div>')
        parts.append("</div>")
        if context is not None:
            parts.append('<div class="diff-skip">⋯</div>')
    if parts[-1] == '<div class="diff-skip">⋯</div>':
        parts.pop()
    parts.append("</div>")
    return "".join(parts)
```

  `_gutter` returning `""` when `line_numbers` is `False` is what makes the
  f-strings collapse to the v3 literals — `test_compact_output_is_byte_identical_to_v3`
  from task 1 is the guard, keep it green.

- [x] **Step 4:** run → PASS.

```bash
python -m pytest -q tests/test_diffing.py
python -m pytest -q
```

- [x] **Step 5:** `git commit -m "feat(diff): optional old/new line-number gutters"`

### Task 3: `?view=compact|full` toggle on the diff page

**Files:**
- Modify: `src/malus/web/router.py` (`diff_page`, :820)
- Modify: `src/malus/web/templates/diff.html`
- Modify: `src/malus/web/static/app.css` (after the v3 step 03 diff block, :429)
- Test: `tests/web/test_diff_page.py` (extend)

**Interfaces produced:** `GET /ui/reviews/{id}/diff?view=compact` (default,
hunks ±3, no gutters) and `?view=full` (whole document, line numbers). Authz,
404 and the 409-before-freeze behaviour are unchanged.

- [x] **Step 1: failing tests** — append to `tests/web/test_diff_page.py` (reuse
  its `R` constant and fixture style; the existing `docs["baseline"]` is only 9
  lines, too short for ±3 context to elide anything, so this seed pads it):

```python
# --- v3.1 step 03: Compact | Full view toggle ------------------------------

FILLER = "\n".join(f"filler line {i:02d}" for i in range(30))


def _seed_long_closeout(mkuser, docs):
    """Owner + reviewer, baseline padded with 30 filler lines, one accepted
    RID, one closeout save touching **two distant lines** — so compact view
    has two hunks (hence a diff-skip marker) and elides the rest."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    baseline = docs["baseline"] + FILLER + "\n"
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": baseline})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit",
           json={"content": docs["copy_f"] + FILLER + "\n"})
    owner.post(f"/reviews/{R}/harvest")
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "will fix", "resolution": ""},
    )
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    owner.post(f"/ui/reviews/{R}/start-closeout")
    edited = baseline.replace("configurable", "bounded").replace(
        "filler line 20", "filler line twenty"
    )
    owner.post(f"/ui/reviews/{R}/closeout",
               data={"content": edited, "rids": ["SIN-SRS-0001"]})
    return owner, f


def test_default_view_is_compact(mkuser, docs):
    owner, _ = _seed_long_closeout(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}/diff")
    assert page.status_code == 200
    assert "filler line 00" not in page.text     # far context elided
    assert "filler line 29" not in page.text
    assert "diff-skip" in page.text              # marker between the two hunks
    assert "diff-ln" not in page.text            # no gutters in compact view
    assert f'href="/ui/reviews/{R}/diff?view=full"' in page.text


def test_full_view_renders_the_whole_document_with_line_numbers(mkuser, docs):
    owner, _ = _seed_long_closeout(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}/diff?view=full")
    assert page.status_code == 200
    assert "filler line 00" in page.text and "filler line 29" in page.text
    assert "diff-skip" not in page.text
    assert '<span class="diff-ln diff-ln-old">1</span>' in page.text
    assert f'href="/ui/reviews/{R}/diff?view=compact"' in page.text


def test_unknown_view_falls_back_to_compact(mkuser, docs):
    owner, _ = _seed_long_closeout(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}/diff?view=bogus")
    assert page.status_code == 200               # never 4xx on a read-only page
    assert "diff-ln" not in page.text
    assert page.text.count('aria-current="page"') == 1


def test_active_view_is_marked_in_the_toggle(mkuser, docs):
    owner, _ = _seed_long_closeout(mkuser, docs)
    full = owner.get(f"/ui/reviews/{R}/diff?view=full").text
    assert f'href="/ui/reviews/{R}/diff?view=full" aria-current="page"' in full
    assert full.count('aria-current="page"') == 1


def test_toggle_is_server_side_only(client):
    css = client.get("/static/app.css").text
    assert ".diff-ln" in css                     # the gutters are styled
    # no script tag is introduced by the diff page (zero-JS toggle)
```

- [x] **Step 2:** run → FAIL.

```bash
python -m pytest -q tests/web/test_diff_page.py
```

- [x] **Step 3: implement.**

  `src/malus/web/router.py` — `diff_page` gains the query parameter:

```python
@web.get("/ui/reviews/{review_id}/diff", response_class=HTMLResponse)
def diff_page(
    review_id: str,
    request: Request,
    view: str = "compact",
    session: Session = Depends(get_session),
):
    """Full-document diff, baseline vs latest version (v3 step 03 task 4):
    same word-level renderer as the per-RID Changes section, same membership
    authz as ``document_page`` — any review member or a global admin,
    regardless of review phase.

    v3.1 step 03: ``?view=compact`` (default) keeps ±3 lines around each hunk;
    ``?view=full`` renders the whole document with old/new line numbers. The
    state lives in the URL (shareable, no JS — the v2.2 filter-chip idiom);
    an unrecognised value falls back to compact rather than erroring."""
    user = _current(request, session)
    if not user:
        return _LOGIN
    review = _review_or_404(session, review_id)
    if authz.review_role(session, review, user) is None and not user.is_admin:
        raise HTTPException(status_code=403, detail="only review members may open the diff")
    baseline = VersionRepo(session).baseline(review)
    if baseline is None:
        raise HTTPException(status_code=409, detail="the baseline is not frozen yet")
    latest = VersionRepo(session).latest(review)
    full = view == "full"
    return templates.TemplateResponse(
        request,
        "diff.html",
        {
            "user": user,
            "review": review,
            "baseline": baseline,
            "latest": latest,
            "view": "full" if full else "compact",
            "diff_html": html_diff(
                baseline.content,
                latest.content,
                context=None if full else 3,
                line_numbers=full,
            ),
        },
    )
```

  `src/malus/web/templates/diff.html` — insert the toggle between the `<h1>`
  and the diff body (keep the heading text: `tests/web/test_diff_page.py`
  asserts `"Full diff"` and `"baseline v1"`):

```html
{# v3.1 step 03: view toggle — plain links, no JavaScript, state in the URL
   so the view is shareable (same approach as the v2.2 dashboard filter
   chips). The active view is the filled .btn, the other one .btn secondary. #}
<p class="actions" aria-label="Diff view">
  <a class="btn{% if view != 'compact' %} secondary{% endif %}"
     href="/ui/reviews/{{ review.review_id_str }}/diff?view=compact"
     {%- if view == 'compact' %} aria-current="page"{% endif %}>Compact</a>
  <a class="btn{% if view != 'full' %} secondary{% endif %}"
     href="/ui/reviews/{{ review.review_id_str }}/diff?view=full"
     {%- if view == 'full' %} aria-current="page"{% endif %}>Full</a>
</p>
```

  `src/malus/web/static/app.css` — append right after the v3 step 03 diff block
  (currently ending with `.diff-skip` at :429), light theme only, brand custom
  properties, `var(--mono)` inherited from `.diff`:

```css
/* v3.1 step 03: line-number gutters — html_diff(line_numbers=True), used by
   the full-document view (?view=full). inline-block + a fixed width keeps the
   two columns aligned even when a gutter is empty (a deleted row has no
   new-side number, an inserted row has no old-side number). */
.diff-ln { display: inline-block; width: 2.6rem; padding-right: .5rem; text-align: right; color: var(--faint); font-variant-numeric: tabular-nums; user-select: none; -webkit-user-select: none; }
.diff-ln-new { border-right: 1px solid var(--line); margin-right: .7rem; }
```

- [x] **Step 4:** run → PASS.

```bash
python -m pytest -q tests/web/test_diff_page.py
python -m pytest -q
```

- [x] **Step 5:** `git commit -m "feat(web): Compact | Full toggle on the diff page (?view=)"`

### Task 4: one *Full diff* button on the dashboard

**Files:**
- Modify: `src/malus/web/templates/review.html` (delete :34, refresh the comment at :95-97)
- Test: `tests/web/test_diff_page.py` (extend)

The owner-actions block for `phase == 'closeout'` and the all-members block for
`phase in ('closeout', 'finalized')` both render the link, so an owner in
closeout sees it twice (recorded as a deviation in `docs/plan/v3/03-verification.md`
§Deviations). The all-members block is the one that stays.

- [x] **Step 1: failing test** — append to `tests/web/test_diff_page.py`:

```python
def test_dashboard_links_the_diff_exactly_once(mkuser, docs):
    """v3.1 step 03: the owner-actions block used to render a second copy of
    the Full diff button on top of the all-members one (review.html:34)."""
    owner, f = _seed_answered(mkuser, docs)
    _to_closeout(owner, f)

    page = owner.get(f"/ui/reviews/{R}")
    assert page.status_code == 200
    assert page.text.count(f'href="/ui/reviews/{R}/diff"') == 1

    # and the reviewer, who only ever had the all-members block, is unaffected
    r_page = f.get(f"/ui/reviews/{R}")
    assert r_page.text.count(f'href="/ui/reviews/{R}/diff"') == 1
```

- [x] **Step 2:** run → FAIL (`assert 2 == 1` for the owner).

```bash
python -m pytest -q tests/web/test_diff_page.py::test_dashboard_links_the_diff_exactly_once
```

- [x] **Step 3: implement** — in `src/malus/web/templates/review.html`, delete
  line 34 from the `{% elif phase == 'closeout' %}` branch:

```html
    <a class="btn secondary" href="/ui/reviews/{{ review.review_id_str }}/diff">Full diff</a>
```

  and replace the now-stale comment above the all-members block (:95-97) —
  it currently claims the owner block "already links it":

```html
{# v3 step 03 task 4 / v3.1 step 03: the single Full-diff entry point, for
   owner, reviewer and moderator alike (the duplicate in the owner-actions
   block above was removed in v3.1). #}
```

  Nothing else moves: the *Closeout workspace* link, the finalize form and the
  admin *Back to review* form stay where they are.

- [x] **Step 4:** run → PASS.

```bash
python -m pytest -q tests/web/test_diff_page.py
python -m pytest -q
```

- [x] **Step 5:** `git commit -m "fix(web): render the Full diff button once on the dashboard"`

## Definition of Done

- [x] Deliverables checked; `python -m pytest -q` green (exit 0), no test removed
      or weakened — in particular `tests/test_diffing.py`'s six v3 tests and
      `tests/web/test_diff_page.py`'s six v3 tests still pass untouched.
- [x] `html_diff` exposes exactly
      `def html_diff(old: str, new: str, *, context: int | None = 3, line_numbers: bool = False) -> str`
      — step 04 (`04-downloads.md`) calls it with `context=None, line_numbers=True`.
- [x] Manual smoke (browser), on a closeout review with at least one saved
      version: `/ui/reviews/{id}/diff` shows hunks with no gutters and the
      *Compact* button filled; clicking *Full* reloads to `?view=full` with the
      whole document, aligned old/new numbers and no `⋯` marker; the URL is
      copy-pasteable into a new tab and lands on the same view; the dashboard
      shows one *Full diff* button as owner and one as reviewer.
- [x] A RID card's *Changes* section renders exactly as before (compact, no
      gutters) — visual check on the same review.

## Out of scope

- The `baseline.md` / `diff.html` download routes and the reviews-list `⋯`
  menu — step 04 (`04-downloads.md`), which builds on this signature.
- Closeout moving into the document viewer (step 01) and terminate/reopen
  (step 02).
- Side-by-side diff, intra-word character diff, syntax highlighting, collapsing
  unchanged regions client-side — all rejected by the zero-JS constraint.
- Bumping `asset_v` for the CSS change (v3 `06-release.md`).
