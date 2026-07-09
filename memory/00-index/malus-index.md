---
title: maluS — Index
type: project
permalink: malus/00-index/malus-index
world: ALUM
source: chat
status: active
tags:
- malus
- index
- review
- rid
---

# maluS — Index

Document review management application for Markdown documents, modeled on
aerospace-style RID (Review Item Discrepancy) processes. Repo:
`~/Documents/ALUM/maluS`, GitHub `albertoboffi-ALUM/maluS` (public).

## Observations
- [overview] Full review cycle on a Markdown DUR: freeze baseline → per-reviewer copies with inline comment blocks → harvest into rtd.yaml → triage/dedup → owner disposition via single-file HTML GUI → RID-referenced implementation → reviewer-side verification → finalize #process
- [overview] Two operating modes, symmetric by design: AI as document owner with human reviewers, or human owner with human and AI reviewers #modes
- [constraint] Zero paid software anywhere in the workflow — worst case a text editor, normal case a browser #constraint
- [naming] Name maluS chosen by Alberto (2026-07-03) over candidates Alumend/Alumina/Alumark; Alumark was already taken by his GTK4 screenshot app #naming
- [structure] Repo layout: docs/plan (one MD per step), src/malus (Python package), gui/rtd.html (single-file GUI), tests, memory (this basic-memory project) #structure
- [plan] Seven development steps: foundations, harvest, triage, GUI, lifecycle, AI roles, end-to-end — see docs/plan/00-general-plan.md #plan

## Relations
- part_of [[ALUM]]
- documented_by [[Architecture Decisions 2026-07-03]]
- specified_by [[Comment Syntax Spec]]
- specified_by [[RID Schema and Lifecycle]]

## Sources
- Claude chat design session, 2026-07-03 (process design and architecture review)
