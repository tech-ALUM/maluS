# Step 6 — Web GUI: Markdown Editor & Reviewer Workflow

## Objective

Bring document authoring and reviewing fully into the browser: an in-app
Markdown editor for reviewers (comment blocks only) and for the owner
(implementation), with live preview.

## Deliverables

- [ ] CodeMirror 6 Markdown editor embedded (vendored, no runtime CDN)
- [ ] Reviewer mode: open own copy, insert `{COMM|…}` / `{SUGG:…}` blocks;
      the editor assists block insertion and the freeze rule is enforced
      (baseline text is read-only; only comment-block insertions are allowed),
      re-validated server-side by the existing parser on submit
- [ ] Owner mode: edit the DUR for accepted findings, creating a new version and
      linking the edit to its RIDs (produces `RidChange` rows)
- [ ] Live Markdown preview; unsaved-changes guard
- [ ] Submit-copy flow that triggers harvest server-side
- [ ] Tests: rejected tampering, valid submission, edit→version→RID link

## Key behaviors

- The freeze rule is a first-class editor constraint, not a convention: a
  reviewer literally cannot alter baseline text, only add blocks. The server
  still re-checks (defense in depth).
- Owner implementation edits are captured as versions with mandatory RID links,
  which is what satisfies the Step-2 traceability check (no git needed).

## Definition of Done

A reviewer comments and submits, and an owner implements accepted findings,
entirely in the browser; tampering is rejected at both layers; every accepted
RID that is implemented has a linked change; suite green.

## Out of scope

AI-authored copies (Step 7). Real-time co-editing (single-writer per copy holds).

## Sources

v1 design session 2026-07-09.
