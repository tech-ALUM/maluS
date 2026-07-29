# v3 Step 3 — Reviewer verification: per-RID diff

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a reviewer clicking their comment in closeout sees exactly which
Markdown changes were made for it — a server-side word-level diff per linked
version — and verifies (or requests changes) right under the diff. Plus a
full-diff page (baseline ↔ latest).

**Architecture:** new pure module `src/malus/diffing.py` built on stdlib
`difflib` (zero new dependencies — spec §Per-RID diff). The server computes and
escapes the diff HTML; the viewer injects it into the RID card (still passed
through DOMPurify, defense in depth). Verify/Request-changes buttons exist
since step 01; here they gain the Changes context.

**Tech stack:** Python `difflib`, Jinja, vanilla JS. Depends on steps 01–02.

## Global constraints

- No new dependencies, no new vendored JS (ADR 0003 untouched).
- All diff HTML is built server-side from **escaped** text (`html.escape`)
  before markup insertion — never interpolate raw document text into HTML.
- Suite green + Conventional Commit per task.

## Deliverables

- [ ] `diffing.py`: word-level unified diff → HTML (`<ins>`/`<del>`, ±3 lines context)
- [ ] Per-RID `changes` payload in `_document_context` + card Changes section
- [ ] Full-diff page `GET /ui/reviews/{id}/diff`
- [ ] CSS for ins/del/diff blocks
- [ ] Full suite green

---

### Task 1: the diff module

**Files:**
- Create: `src/malus/diffing.py`
- Test: `tests/test_diffing.py` (new)

**Interfaces produced:**

```python
def html_diff(old: str, new: str, *, context: int = 3) -> str
    """Line-grouped, word-refined diff as safe HTML (empty string if equal)."""
```

- [ ] **Step 1: failing tests:**

```python
from malus.diffing import html_diff


def test_equal_texts_yield_empty():
    assert html_diff("a\nb\n", "a\nb\n") == ""


def test_word_level_ins_del():
    out = html_diff("the quick fox\n", "the slow fox\n")
    assert "<del>quick</del>" in out and "<ins>slow</ins>" in out


def test_html_is_escaped():
    out = html_diff("safe\n", "<script>alert(1)</script>\n")
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_context_is_limited():
    old = "\n".join(f"line {i:02d}" for i in range(50)) + "\n"
    new = old.replace("line 10", "line ten").replace("line 40", "line forty")
    out = html_diff(old, new)
    assert "line 07" in out and "line 13" in out       # ±3 kept around hunk 1
    assert "line 25" not in out                        # far context elided
    assert "diff-skip" in out                          # marker between the two hunks
```

- [ ] **Step 2:** run → FAIL. **Step 3: implement** `src/malus/diffing.py`:

```python
"""Server-side diff rendering for the v3 closeout verification (stdlib only).

`html_diff` renders old→new as blocks of context lines plus changed lines with
word-level <ins>/<del> refinement. All text is HTML-escaped before any markup
is added, so the result is safe to inject into the viewer (which additionally
runs DOMPurify — defense in depth).
"""

from __future__ import annotations

import difflib
import html
import re

_WORDS = re.compile(r"\s+|\w+|[^\w\s]", re.UNICODE)


def _split_words(line: str) -> list[str]:
    return _WORDS.findall(line)


def _refine(old_line: str, new_line: str) -> tuple[str, str]:
    """Word-level <del>/<ins> markup for one replaced line pair."""
    old_w, new_w = _split_words(old_line), _split_words(new_line)
    sm = difflib.SequenceMatcher(a=old_w, b=new_w, autojunk=False)
    del_out, ins_out = [], []
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        a_txt = html.escape("".join(old_w[a1:a2]))
        b_txt = html.escape("".join(new_w[b1:b2]))
        if op == "equal":
            del_out.append(a_txt)
            ins_out.append(b_txt)
        else:
            if a_txt:
                del_out.append(f"<del>{a_txt}</del>")
            if b_txt:
                ins_out.append(f"<ins>{b_txt}</ins>")
    return "".join(del_out), "".join(ins_out)


def html_diff(old: str, new: str, *, context: int = 3) -> str:
    if old == new:
        return ""
    old_lines, new_lines = old.splitlines(), new.splitlines()
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    parts: list[str] = ['<div class="diff">']
    for group in sm.get_grouped_opcodes(context):
        parts.append('<div class="diff-hunk">')
        for op, a1, a2, b1, b2 in group:
            if op == "equal":
                for line in old_lines[a1:a2]:
                    parts.append(f'<div class="diff-ctx">{html.escape(line)}</div>')
            elif op == "replace" and (a2 - a1) == (b2 - b1):
                for o, n in zip(old_lines[a1:a2], new_lines[b1:b2]):
                    d, i = _refine(o, n)
                    parts.append(f'<div class="diff-del">{d}</div>')
                    parts.append(f'<div class="diff-ins">{i}</div>')
            else:
                for line in old_lines[a1:a2]:
                    parts.append(f'<div class="diff-del"><del>{html.escape(line)}</del></div>')
                for line in new_lines[b1:b2]:
                    parts.append(f'<div class="diff-ins"><ins>{html.escape(line)}</ins></div>')
        parts.append("</div>")
        parts.append('<div class="diff-skip">⋯</div>')
    if parts[-1] == '<div class="diff-skip">⋯</div>':
        parts.pop()                              # no trailing elision marker
    parts.append("</div>")
    return "".join(parts)
```

  (With grouped opcodes the elision marker sits *between* hunks — the test
  above creates two hunks precisely so the marker appears.)
- [ ] **Step 4:** run → PASS. **Step 5:** `git commit -m "feat(diff): stdlib word-level HTML diff for closeout verification"`

### Task 2: per-RID changes in the viewer payload

**Files:**
- Modify: `src/malus/web/router.py` (`_document_context` :535-627)
- Modify: `src/malus/services/core.py` (new query helper)
- Test: `tests/web/test_document_changes.py` (new)

**Interfaces produced:**

```python
def rid_changes(session, review, rid_id) -> list[dict]
# [{"ordinal": int, "created": iso-ts, "note": str|None,
#   "diff_html": str}]  — one per post-baseline RidChange, diff vs the
#                          version's predecessor (ordinal - 1)
```

  and in the viewer payload each RID dict gains
  `"changes": [...]` (same shape, camelCase `diffHtml`) — only in phase
  `closeout`/`finalized` and only for accepted RIDs, else `[]`.

- [ ] **Step 1: failing test:** closeout review, one accepted RID, one linked save
  changing "quick"→"slow": GET `/ui/reviews/{id}/document` as the RID's reviewer →
  the embedded `#viewer-data` JSON has `rids[i].changes[0].diffHtml` containing
  `<ins>slow</ins>`; a rejected RID has `changes == []`; in phase `in_review`
  every RID has `changes == []`.
- [ ] **Step 2:** run → FAIL. **Step 3: implement:**
  - service `rid_changes` in `core.py`: reuse `_post_baseline_changes`, and for
    each change fetch the predecessor version by ordinal
    (`VersionRepo(session).by_ordinal(review, v.ordinal - 1)` — add this
    one-query repo method beside `latest`) and call
    `diffing.html_diff(prev.content, v.content)`.
  - `_document_context`: when `review.status in (ReviewStatus.CLOSEOUT.value,
    ReviewStatus.FINALIZED.value)` and `r.disposition is Disposition.ACCEPTED`,
    set `"changes": [{"ordinal": c["ordinal"], "created": c["created"],
    "note": c["note"], "diffHtml": c["diff_html"]} for c in svc.rid_changes(...)]`,
    else `"changes": []`.
- [ ] **Step 4:** run → PASS. **Step 5:** `git commit -m "feat(web): per-RID change diffs in the viewer payload"`

### Task 3: Changes section in the RID card

**Files:**
- Modify: `src/malus/web/static/document-viewer.js` (`cardEl`, before the actions block)
- Modify: `src/malus/web/static/app.css`
- Test: `tests/web/test_document_changes.py` (extend: served JS contains the
  `cp-changes` renderer; payload already covered)

- [ ] **Step 1: implement** in `cardEl`, after the reply/resolution block and before
  the actions row:

```js
    if (r && r.changes && r.changes.length) {
      var chWrap = document.createElement("div");
      chWrap.className = "cp-changes";
      var chTitle = document.createElement("div");
      chTitle.className = "cp-changes-title";
      chTitle.textContent = "Changes (" + r.changes.length + ")";
      chWrap.appendChild(chTitle);
      r.changes.forEach(function (ch) {
        var block = document.createElement("div");
        block.className = "cp-change";
        var head = document.createElement("div");
        head.className = "cp-change-head";
        head.textContent = "v" + ch.ordinal + (ch.note ? " — " + ch.note : "");
        block.appendChild(head);
        var body = document.createElement("div");
        // server-built, escaped diff; DOMPurify pass = defense in depth
        body.innerHTML = window.DOMPurify
          ? window.DOMPurify.sanitize(ch.diffHtml)
          : ch.diffHtml;
        block.appendChild(body);
        chWrap.appendChild(block);
      });
      card.appendChild(chWrap);
    }
```

  CSS (`app.css`, match the card idiom):

```css
.cp-changes { margin-top: .5rem; font-size: .85em; }
.cp-changes-title { font-weight: 600; margin-bottom: .25rem; }
.diff { font-family: var(--mono, monospace); white-space: pre-wrap; overflow-x: auto; }
.diff-ctx { opacity: .65; }
.diff-del { background: color-mix(in srgb, crimson 12%, transparent); }
.diff-ins { background: color-mix(in srgb, seagreen 14%, transparent); }
.diff del { color: crimson; text-decoration: line-through; }
.diff ins { color: seagreen; text-decoration: none; font-weight: 600; }
.diff-skip { text-align: center; opacity: .5; }
```

- [ ] **Step 2:** manual check via the E2E fixture review (see DoD) + suite → PASS.
- [ ] **Step 3:** `git commit -m "feat(web): Changes section renders per-RID diffs in the card"`

### Task 4: full-diff page

**Files:**
- Modify: `src/malus/web/router.py`
- Create: `src/malus/web/templates/diff.html`
- Test: `tests/web/test_diff_page.py` (new)

**Interfaces produced:** `GET /ui/reviews/{id}/diff` (member/admin only) —
baseline vs latest version, whole document, same `html_diff` renderer, link
back from the dashboard and the closeout workspace.

- [ ] **Step 1: failing test:** member GET → 200 containing `<ins>`; non-member → 403;
  identical baseline/latest → page shows "No changes yet".
- [ ] **Step 2:** run → FAIL. **Step 3: implement** — route mirrors `document_page`
  authz (member or admin); context: `diff_html = html_diff(baseline.content,
  latest.content)`; template extends `base.html`, prints the crumb, `Full diff
  — baseline v{{ baseline.ordinal }} → v{{ latest.ordinal }}`, then
  `{{ diff_html | safe }}` (it is server-escaped) or the empty-state paragraph.
  Add a `Full diff` link in `review.html` (phase `closeout`/`finalized`, all
  members) and in `closeout.html`'s header line.
- [ ] **Step 4:** run → PASS. **Step 5:** `git commit -m "feat(web): full-diff page (baseline vs latest)"`

## Definition of Done

- [ ] Deliverables checked; `python -m pytest -q` green.
- [ ] Manual smoke: closeout review → reviewer opens their accepted comment →
  card shows Changes with word-level ins/del → Verify moves it to verified;
  Request changes sends it back with the reason visible in the owner's queue
  (step 02) → owner re-saves → new diff appears appended.

## Out of scope

Finalize, downloads, PDF (04); signing (05).
