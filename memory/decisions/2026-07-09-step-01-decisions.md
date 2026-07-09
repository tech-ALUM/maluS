---
title: Step 1 Decisions 2026-07-09
type: decision
permalink: malus/decisions/2026-07-09-step-01-decisions
world: ALUM
source: chat
status: accepted
tags:
- malus
- decision
- spec
- step-1
---

# Step 1 Decisions 2026-07-09

Decisions settled with Alberto Boffi while writing the normative Step 1
contracts (`docs/spec/comment-syntax.md`, `docs/spec/rid-schema.md`). The two
open questions carried in [[Comment Syntax Spec]] are now resolved; the rest
are spec-completions and scoping choices recorded for traceability.

## Observations
- [decision] Fourth `{COMM}` type is `process` (not `question`); a `process`
  finding concerns compliance/structure/the review process. Resolves the
  process-vs-question open question; frozen in docs/spec/comment-syntax.md #comm
- [decision] `{SUGG}` is mechanical-only — no rationale/parameter; a reviewer
  who must justify a change attaches a neighbouring `{COMM}`. Keeps SUGG
  batch-appliable and safely de-duplicable (D4) #sugg
- [spec] Escaping completion beyond memory's `\}`: `\"` denotes a literal quote
  inside `{SUGG}` operands, and any other backslash is literal; a block ends at
  the first unescaped `}` and blocks do not nest #escaping
- [scope] Step 1 `transition()` enforces the status graph + the closure-authority
  invariant only; disposition-conditional routing (accepted→implemented,
  {rejected,deferred}→verified), the traceability rule, and finalize gating are
  documented normative in docs/spec/rid-schema.md but enforced in Step 5 #lifecycle
- [open-question] The frozen RID schema has no dedicated `old`/`new` field for a
  `{SUGG}`; implemented verbatim (the `comment` field renders the change) —
  whether to add explicit fields is flagged for Step 2 #schema

## Relations
- decides_for [[maluS — Index]]
- refines [[Comment Syntax Spec]]
- refines [[RID Schema and Lifecycle]]
- constrained_by [[Architecture Decisions 2026-07-03]]

## Sources
- Claude Code session with Alberto Boffi, 2026-07-09 (Step 1 implementation)
- docs/spec/comment-syntax.md, docs/spec/rid-schema.md (normative contracts)
- docs/plan/01-foundations.md (## Deviations)
