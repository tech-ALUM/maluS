---
title: RID Schema and Lifecycle
type: spec
permalink: malus/specs/rid-schema-and-lifecycle
world: ALUM
source: chat
status: draft
tags:
- malus
- spec
- rid
- lifecycle
---

# RID Schema and Lifecycle

Canonical store rtd.yaml: meta header (review_id, document, baseline_sha,
created, owner, reviewers) + rids list. Normative version in
docs/spec/rid-schema.md (Step 1 deliverable).

## Observations
- [spec] RID id format <PROJECT>-<DOC>-<NNNN> (e.g. SIN-SRS-0042), assigned in document order at first harvest, stable across re-harvests via (reviewer, content-hash) matching; vanished comments become withdrawn, never deleted #ids
- [spec] RID fields: rid, reviewer, created, anchor{section, quote, line_hint}, kind COMM|SUGG, type, severity, status, comment, reply, disposition accepted|rejected|deferred, resolution, master, duplicates[], verified_by, verified_on #schema
- [spec] Lifecycle: open → answered → implemented → verified; rejected/deferred skip implemented (answered → verified = reviewer acknowledges disposition); withdrawn only from open and only by the RID's reviewer #lifecycle
- [spec] Transition table is data (constants.py), single source of truth shared by CLI and GUI #enforcement
- [invariant] Only the reviewer (or moderator on their behalf) may set verified — never the owner; AI may never set verified regardless of seat #closure-authority
- [spec] Traceability: an accepted RID requires ≥1 commit referencing it between baseline SHA and HEAD before it can become implemented #traceability
- [spec] Finalize requires all RIDs verified or withdrawn; deferred RIDs export to a carry-over file for the next review cycle #finalize

## Relations
- specifies [[maluS — Index]]
- constrained_by [[Architecture Decisions 2026-07-03]]

## Sources
- Claude chat design session, 2026-07-03
