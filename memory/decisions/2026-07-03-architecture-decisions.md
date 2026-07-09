---
title: Architecture Decisions 2026-07-03
type: decision
permalink: malus/decisions/2026-07-03-architecture-decisions
world: ALUM
source: chat
status: accepted
tags:
- malus
- decision
- architecture
---

# Architecture Decisions 2026-07-03

Five decisions from the founding design session, correcting weaknesses in
the initial process draft.

## Observations
- [decision] D1 Freeze rule: reviewer copies may ONLY receive inserted comment blocks, never text edits — consolidation becomes diff-extraction instead of an N-way merge; implemented as per-reviewer git branches harvested, never merged #freeze
- [decision] D2 Single canonical RTD: rtd.yaml is the only maintained artifact; the annotated merged DUR and any pretty table/dashboard are generated views — two hand-maintained representations would desynchronize by cycle two #rtd
- [decision] D3 Reviewer-side closure: reviewers (never the owner) verify and close RIDs; statuses open→answered→implemented→verified; THE critical control making AI-owner mode safe — owner self-certification is structurally impossible #lifecycle
- [decision] D4 Differentiated comments: {SUGG: "old" -> "new"} mechanical suggestions are batch-appliable and deduplicated automatically; only {COMM} findings generate discussion-grade RIDs; triage clusters duplicates under master RIDs before disposition #triage
- [decision] D5 Three-roles abstraction: owner, reviewer, moderator — each seat fillable by human or AI; this abstraction (not file formats) is what makes the process mode-agnostic #roles
- [decision] Storage: single rtd.yaml + self-contained rtd.html GUI, after Alberto rejected one-file-per-RID as excessive; safe because the workflow is single-writer-per-phase (reviewers never write the RTD; harvest writes once; then owner is sole writer; then verification) #storage
- [decision] JSONL variant explicitly rejected for current scale (no very large reviews expected) #storage
- [context] Process lineage: ECSS/aerospace RID-based document review, deliberately kept #lineage

## Relations
- decides_for [[maluS — Index]]

## Sources
- Claude chat design session with Alberto Boffi, 2026-07-03
