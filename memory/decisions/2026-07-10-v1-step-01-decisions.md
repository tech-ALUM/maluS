---
title: v1 Step 1 — Architecture & Data Model Decisions
type: decision
permalink: malus/decisions/2026-07-10-v1-step-01-decisions
world: ALUM
source: claude-code
status: accepted
tags:
- malus
- decision
- v1
- data-model
- architecture
---

# v1 Step 1 — Architecture & Data Model Decisions

Decisions taken implementing v1 Step 1 (docs/plan/v1/01-architecture-and-data-model.md).
The v0 domain invariants D1–D5 are unchanged and preserved.

## Observations

- [decision] ADR 0001 (docs/adr/0001-v1-web-pivot.md): drop git as store/transport; the DB is canonical; freeze becomes an immutable DocumentVersion (content hash); RID traceability becomes RidChange + AuditLog; rtd.yaml demoted to import/export; AI reviewer free via interactive Claude Code over MCP (paid headless engine only behind an off-by-default flag) #adr #pivot
- [decision] ADR 0002 (docs/adr/0002-stack.md): Python 3.12 + FastAPI + SQLModel/SQLite(WAL, Postgres-ready) + Alembic + argon2 + MCP; deps added per-step, Step 1 adds only sqlmodel + alembic #adr #stack
- [decision] Repo relocated to ~/Documents/ALUM/maluS (the plan's home); the duplicate ~/Documents/ALUM/code/maluS was removed. Do not recreate code/maluS #repo
- [decision] Names round-trip losslessly via User.display_name; owner/reviewer/verified_by/created_by are User FKs; import creates placeholder Users by display_name (no auth yet, matched/deduplicated) #mapping
- [decision] review_members is a concrete table now (schema only); review-scoped RBAC roles are enforced at Step 4 #rbac
- [decision] reviews.rid_prefix added so meta.rid_prefix round-trips; meta.baseline_sha maps to the baseline DocumentVersion.content_hash, preserved verbatim for v0 imports (which carry no content) #mapping
- [decision] RID.duplicates is NOT stored — derived from the master_id inverse; export recomputes it in document order #rid
- [decision] Enum values stay owned by malus.constants and are stored as plain .value strings (not SQL Enum types); the rtd_io mapping layer converts. reviews.status uses a provisional ReviewStatus enum (draft/active/finalized) in db/, not the frozen constants; full review lifecycle refined later #enums
- [decision] Table named users (not user) for PostgreSQL reserved-word safety; SQLite runs with PRAGMA foreign_keys=ON and WAL for file-based DBs #schema
- [context] Lossless rtd.yaml <-> DB proven both directions (byte-identical canonical YAML, cross-DB idempotence) in tests/db/test_db_mapping.py; the initial Alembic migration is verified to apply on a fresh SQLite file and match the model metadata exactly #testing
- [context] DB-layer tests are tests/db/test_db_*.py; the db_ prefix avoids a pytest module-name clash with the existing tests/test_models.py #testing
- [context] docs/usage.md was already deleted in the working tree at session start; left untouched (out of Step-1 scope) #housekeeping

## Relations
- implements [[maluS — Index]]
- supersedes storage/transport parts of [[Architecture Decisions 2026-07-03]] (D1 git-branch freeze, git traceability); D1–D5 domain invariants retained
- specified_by [[v1 Data Model]] (docs/spec/data-model.md)

## Sources
- docs/plan/v1/00-overview.md, docs/plan/v1/01-architecture-and-data-model.md (v1 design session 2026-07-09)
- docs/adr/0001-v1-web-pivot.md, docs/adr/0002-stack.md
- Implementation: src/malus/db/ (models, session, rtd_io), alembic/, tests/db/
- Claude Code session with Alberto Boffi, 2026-07-10
