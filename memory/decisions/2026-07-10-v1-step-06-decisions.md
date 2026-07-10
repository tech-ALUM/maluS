---
title: v1 Step 6 — Markdown Editor & Reviewer Workflow Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-06-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- gui
- editor
---

# v1 Step 6 — Markdown Editor & Reviewer Workflow Decisions

Document authoring/reviewing in the browser (docs/plan/v1/06-gui-editor-reviewer.md).

## Observations

- [decision] Editor is a textarea with {COMM}/{SUGG} insert helpers + a vendored `marked` live preview + an unsaved-changes guard — NOT CodeMirror 6, which needs a bundling step that violates the "no build step / vendored / no CDN" constraint. CM6 can replace it later behind a build #editor
- [decision] Freeze rule is enforced authoritatively server-side (validate_insertion_only rejects baseline-text edits -> 422) plus a best-effort client-side pre-check (strip blocks, compare residue to baseline). A textarea can't make baseline ranges literally read-only; the server is the guarantee #freeze
- [decision] Submitting a reviewer copy validates -> saves -> re-harvests as a server-side side effect (reviewer authorized for their own copy; the harvest is automatic, distinct from the moderator-gated API /harvest) #submit
- [decision] Owner 'implement' editor: save the edited DUR -> new DocumentVersion + RidChange links for the ticked accepted RIDs -> advance them to implemented (the linked change satisfies the Step-2 traceability gate) #implement
- [context] Vendored marked@12 (35KB) for preview; htmx already vendored. 154 tests pass; tampering rejected at both layers, valid submit harvests, implement->version->RID-link->verify proven #testing

## Relations
- implements [[maluS — Index]]
- follows [[v1 Step 5 — Web GUI (Dashboard & RTD) Decisions]]
- realises [[v1 Step 2 — Persistence Layer Decisions]] (traceability via RidChange)

## Sources
- docs/plan/v1/06-gui-editor-reviewer.md
- Implementation: src/malus/web/ (edit_copy.html, implement.html, static/editor.js, vendored marked); editor routes in web/router.py
- Claude Code session with Alberto Boffi, 2026-07-10
