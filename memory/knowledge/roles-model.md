---
title: Roles Model
type: note
permalink: malus/knowledge/roles-model
world: ALUM
source: chat
status: active
tags:
- malus
- roles
- ai
---

# Roles Model

Three seats, each fillable by a human or an AI. The abstraction that makes
the process mode-agnostic (D5).

## Observations
- [role] Owner: authors/maintains the DUR, replies and dispositions RIDs, implements accepted changes with RID-referenced commits; cannot verify or close anything #owner
- [role] Reviewer: comments own frozen copy (comment blocks only), later verifies resolution of own RIDs and closes them or reopens with mandatory reason #reviewer
- [role] Moderator: runs harvest and triage, confirms duplicate clusters, may verify on behalf of an unavailable reviewer if delegated #moderator
- [guardrail] AI in any seat: output enters only through validated formats (comment blocks, rtd.yaml fields); every AI artifact attributed (reviewer name or ai-drafted flag); AI never sets verified #guardrails
- [mode] Mode 1 (AI owner + human reviewers): human verification of every disposition/implementation is the mandatory control #mode1
- [mode] Mode 2 (human owner + human/AI reviewers): AI reviewer generates its own copy's comments via malus ai review, validated by the parser before entering harvest #mode2
- [fact] AI engines planned: Claude Code headless (claude -p), Anthropic API, mock engine for tests #engines

## Relations
- part_of [[maluS — Index]]
- constrained_by [[RID Schema and Lifecycle]]

## Sources
- Claude chat design session, 2026-07-03
