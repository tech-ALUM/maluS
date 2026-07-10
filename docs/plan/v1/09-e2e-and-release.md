# Step 9 — End-to-End, Migration & Release v1.0.0

## Objective

Prove the whole product with multiple real users and an AI reviewer, provide a
path off any v0 review, finish the docs, and release v1.0.0.

## Deliverables

- [ ] Scripted multi-user E2E: admin creates users; owner creates a review and
      DUR; reviewers (incl. one AI via MCP) comment; harvest → triage →
      disposition (GUI) → implement (editor) → reviewer verify → report →
      finalize — all over the API/GUI, no git
- [ ] v0 import: load a legacy `rtd.yaml` (and baseline) into the DB
- [ ] `docs/usage.md` rewritten for the web app (both modes); README updated;
      screenshots
- [ ] Version 1.0.0; tag `v1.0.0`; changelog vs v0.1.0
- [ ] `gui/rtd.html` (v0) retained read-only or clearly marked legacy

## Definition of Done

A newcomer, following the docs, deploys maluS, logs in, and runs a full review
with a human and an AI reviewer to a finalized document — without git; the E2E
test is green locally; tagged release pushed.

## Sources

v1 design session 2026-07-09.
