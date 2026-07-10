---
title: v1 Step 9 — E2E, Migration & Release v1.0.0 Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-09-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- release
- e2e
---

# v1 Step 9 — E2E, Migration & Release v1.0.0 Decisions

Prove the product end-to-end, provide a v0 migration path, finish docs, and
release v1.0.0 (docs/plan/v1/09-e2e-and-release.md).

## Observations

- [decision] Multi-user E2E (tests/e2e): admin -> users; owner creates+freezes a review; a human reviewer (API submit) and an AI reviewer (MCP tools, Basic auth) comment; harvest -> triage -> disposition (GUI /ui/dispose) -> implement (GUI editor) -> verify (reviewer via GUI + moderator-on-behalf for the AI via API) -> report -> finalize. No git anywhere. Audit log shows distinct actors #e2e
- [decision] v0 migration: malus.legacy.import_review_dir (the `malus import` CLI) loads baseline.md + rtd.yaml + reviewers/*.md into the DB; rtd.yaml also imports/exports via the API. Proven in the E2E #migration
- [decision] Released v1.0.0: version bumped (pyproject + __init__), CHANGELOG.md vs v0.1.0, tag v1.0.0. README + docs/usage.md rewritten for the web app; docs/usage/ai-reviewer.md for the AI path #release
- [decision] gui/rtd.html retained and clearly marked legacy (top-of-file banner + gui/README.md); v1's interface is the served web app #legacy
- [context] Deviation: screenshots not embedded (browser-preview tooling unavailable here; GUI covered by tests/web). 166 tests pass across db/api/web/mcp/ops/e2e #testing

## Relations
- implements [[maluS — Index]]
- follows [[v1 Step 8 — Deployment & Operations Decisions]]
- completes [[maluS — Index]] v1 (all nine steps)

## Sources
- docs/plan/v1/09-e2e-and-release.md
- Implementation: tests/e2e/, CHANGELOG.md, README.md, docs/usage.md, gui/README.md, version 1.0.0
- Claude Code session with Alberto Boffi, 2026-07-10
