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
`~/Documents/ALUM/maluS`, GitHub `tech-ALUM/maluS` (public).

## Observations
- [overview] Full review cycle on a Markdown DUR: freeze baseline → per-reviewer copies with inline comment blocks → harvest into rtd.yaml → triage/dedup → owner disposition via single-file HTML GUI → RID-referenced implementation → reviewer-side verification → finalize #process
- [overview] Two operating modes, symmetric by design: AI as document owner with human reviewers, or human owner with human and AI reviewers #modes
- [constraint] Zero paid software anywhere in the workflow — worst case a text editor, normal case a browser #constraint
- [naming] Name maluS chosen by Alberto (2026-07-03) over candidates Alumend/Alumina/Alumark; Alumark was already taken by his GTK4 screenshot app #naming
- [structure] Repo layout: docs/plan (one MD per step), src/malus (Python package), gui/rtd.html (single-file GUI), tests, memory (this basic-memory project) #structure
- [plan] v0.1.0 shipped: seven development steps — foundations, harvest, triage, GUI, lifecycle, AI roles, end-to-end — see docs/plan/00-general-plan.md #plan
- [plan] v1 (2026-07 onward) turns maluS into a self-hosted web app: a database replaces git, FastAPI + SQLModel + Alembic, browser GUI + Markdown editor, login/RBAC, and a free interactive-Claude-Code MCP reviewer — see docs/plan/v1/00-overview.md and ADRs 0001/0002 — released v1.0.0 on 2026-07-10 #v1
- [plan] v1.2 (2026-07-11 design) — member management + reviewer onboarding: a searchable account picker (assign by username, no more phantom users), inline role change + member removal with a primary-owner guard, and a reviewer hand-off (shareable link + landing CTA + "to comment" cue). Step 1 (member management) shipped 2026-07-12; see docs/plan/v1.2/ #v1.2

## Relations
- part_of [[ALUM]]
- documented_by [[Architecture Decisions 2026-07-03]]
- documented_by [[v1 Step 1 — Architecture & Data Model Decisions]]
- documented_by [[v1 Step 2 — Persistence Layer Decisions]]
- documented_by [[v1 Step 3 — HTTP API Decisions]]
- documented_by [[v1 Step 4 — Authentication & Roles Decisions]]
- documented_by [[v1 Step 5 — Web GUI (Dashboard & RTD) Decisions]]
- documented_by [[v1 Step 6 — Markdown Editor & Reviewer Workflow Decisions]]
- documented_by [[v1 Step 7 — AI Reviewer via MCP Decisions]]
- documented_by [[v1 Step 8 — Deployment & Operations Decisions]]
- documented_by [[v1 Step 9 — E2E, Migration & Release v1.0.0 Decisions]]
- documented_by [[v1 Step 10 — Account Management GUI Decisions]]
- documented_by [[v1 Step 11 — Caddy in docker-compose Decisions]]
- documented_by [[v1 Step 12 — GUI Review Creation + Login Feedback Decisions]]
- documented_by [[v1.2 Step 1 — Member Management (picker, roles, removal) Decisions]]
- specified_by [[Comment Syntax Spec]]
- specified_by [[RID Schema and Lifecycle]]

## Sources
- Claude chat design session, 2026-07-03 (process design and architecture review)
