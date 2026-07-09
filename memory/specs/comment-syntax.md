---
title: Comment Syntax Spec
type: spec
permalink: malus/specs/comment-syntax
world: ALUM
source: chat
status: draft
tags:
- malus
- spec
- syntax
---

# Comment Syntax Spec

Inline comment blocks are the ONLY modification reviewers may make to
their DUR copy (freeze rule, D1). Normative version will live in
docs/spec/comment-syntax.md (Step 1 deliverable).

## Observations
- [spec] Discussion comment: {COMM|type=<t>|sev=<s>: free text} with type ∈ typo|editorial|technical|process (default editorial) and sev ∈ minor|major|critical (default minor); parameters optional and order-free #comm
- [spec] Mechanical suggestion: {SUGG: "exact old text" -> "new text"} — batch-appliable without discussion, identical SUGGs deduplicate automatically, default disposition proposal accepted #sugg
- [spec] Multi-line content allowed until closing brace; literal } escaped as \} #escaping
- [spec] Blocks may appear anywhere between words/lines; harvest anchors each block to nearest preceding heading + preceding sentence fragment (~120 chars) + baseline line hint #anchoring
- [resolved] Fourth COMM type = process (not question); settled with Alberto 2026-07-09, frozen in docs/spec/comment-syntax.md — see [[Step 1 Decisions 2026-07-09]] #resolved
- [resolved] SUGG has no rationale parameter (mechanical-only); justification goes in a neighbouring COMM; settled with Alberto 2026-07-09 — see [[Step 1 Decisions 2026-07-09]] #resolved

## Relations
- specifies [[maluS — Index]]
- related_to [[RID Schema and Lifecycle]]
- resolved_by [[Step 1 Decisions 2026-07-09]]

## Sources
- Claude chat design session, 2026-07-03
