# v2.1 Step 3 — New review: baseline via .md upload

## Objective

Creating a review uploads the baseline as a Markdown file instead of pasting
text. JSON API unchanged.

## Files

- Modify: `src/malus/web/router.py` — `new_review_submit` takes
  `baseline: UploadFile = File(...)`: require `.md`/`.markdown` filename
  (case-insensitive), ≤ 2 MB, valid UTF-8 — violations re-render the form
  with a 422 and a clear message; empty title defaults to the filename stem.
- Modify: `src/malus/web/templates/new_review.html` — file input
  (`accept=".md,.markdown,text/markdown"`, required), form
  `enctype="multipart/form-data"`; the paste textarea is removed.
- Test: extend `tests/web/test_new_review.py` (multipart happy path, wrong
  extension, oversize, invalid UTF-8, title defaulting).

## Deliverables (TDD)

- [ ] Failing tests as above (upload via `files={"baseline": (name, bytes,
      "text/markdown")}`).
- [ ] Implement route + template.
- [ ] Browser verification: create a review by uploading a real .md.
- [ ] Suite green; commit
      `feat(web): create review by uploading the baseline .md (v2.1 step 3)`.

## Definition of Done

No paste path remains in the GUI; invalid uploads produce a friendly 422;
`POST /reviews` (JSON) untouched.

## Sources

- `00-design.md` decision 5; `python-multipart` already a dependency.
