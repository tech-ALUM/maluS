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
- [plan] v0.1.0 shipped: seven development steps — foundations, harvest, triage, GUI, lifecycle, AI roles, end-to-end — see docs/plan/00-general-plan.md #plan
- [plan] v1 (2026-07 onward) turns maluS into a self-hosted web app: a database replaces git, FastAPI + SQLModel + Alembic, browser GUI + Markdown editor, login/RBAC, and a free interactive-Claude-Code MCP reviewer — see docs/plan/v1/00-overview.md and ADRs 0001/0002 #v1

## Relations
- part_of [[ALUM]]
- documented_by [[Architecture Decisions 2026-07-03]]
- documented_by [[v1 Step 1 — Architecture & Data Model Decisions]]
- documented_by [[v1 Step 2 — Persistence Layer Decisions]]
- documented_by [[v1 Step 3 — HTTP API Decisions]]
- documented_by [[v1 Step 4 — Authentication & Roles Decisions]]
- documented_by [[v1 Step 5 — Web GUI (Dashboard & RTD) Decisions]]
- documented_by [[v1 Step 6 — Markdown Editor & Reviewer Workflow Decisions]]
- specified_by [[Comment Syntax Spec]]
- specified_by [[RID Schema and Lifecycle]]

## Sources
- Claude chat design session, 2026-07-03 (process design and architecture review)
