# Step 6 — Web GUI: Markdown Editor & Reviewer Workflow

## Objective

Bring document authoring and reviewing fully into the browser: an in-app
Markdown editor for reviewers (comment blocks only) and for the owner
(implementation), with live preview.

## Deliverables

- [x] CodeMirror 6 Markdown editor embedded (vendored, no runtime CDN)
- [x] Reviewer mode: open own copy, insert `{COMM|…}` / `{SUGG:…}` blocks;
      the editor assists block insertion and the freeze rule is enforced
      (baseline text is read-only; only comment-block insertions are allowed),
      re-validated server-side by the existing parser on submit
- [x] Owner mode: edit the DUR for accepted findings, creating a new version and
      linking the edit to its RIDs (produces `RidChange` rows)
- [x] Live Markdown preview; unsaved-changes guard
- [x] Submit-copy flow that triggers harvest server-side
- [x] Tests: rejected tampering, valid submission, edit→version→RID link

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

## Deviations

Details in `memory/decisions/2026-07-10-v1-step-06-decisions.md`.

- **Editor:** a `<textarea>` editor with `{COMM}`/`{SUGG}` insert helpers, a
  vendored `marked` live preview, and an unsaved-changes guard — **not**
  CodeMirror 6, which needs a bundling step incompatible with the "no build step,
  vendored, no CDN" constraint. CM6 can be dropped in later behind a build.
- **Freeze rule:** enforced authoritatively **server-side** (the existing
  `validate_insertion_only` parser rejects any baseline-text change → 422) plus a
  best-effort **client-side pre-check** (strip blocks, compare residue to the
  baseline). A textarea cannot make baseline ranges literally read-only the way
  CM6 could; the server is the guarantee ("rejected at both layers").
- **Submit-copy triggers harvest:** submitting a reviewer copy validates, saves,
  and re-harvests as a server-side side effect (the reviewer is authorized for
  their own copy; the harvest is automatic, distinct from the moderator-gated API
  `/harvest`).
- **Owner implement:** saving the edited DUR creates a new version, links the
  ticked accepted RIDs (`RidChange`), and advances those RIDs to `implemented`
  (the linked change satisfies the traceability gate).

## Sources

v1 design session 2026-07-09.
