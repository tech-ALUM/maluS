# Step 1 — Architecture & Data Model

## Objective

Record the v1 architecture as an ADR, define the database schema, and map the
existing domain models onto it — before any web code is written.

## Deliverables

- [ ] `docs/adr/0001-v1-web-pivot.md` — the decision to drop git, adopt a
      DB + web app, and the AI-billing constraint (see Sources)
- [ ] `docs/adr/0002-stack.md` — FastAPI + SQLModel/SQLite(→Postgres) + Alembic
      + argon2 auth + MCP; rationale and rejected alternatives
- [ ] `src/malus/db/` — SQLModel table definitions + engine/session setup
- [ ] Alembic configured; initial migration
- [ ] `docs/spec/data-model.md` — normative schema + how each v0 concept maps
- [ ] Tests: models create, relationships, constraints, enum round-trips

## Schema (normative outline)

- **User**(id, username unique, email, password_hash, is_active, created)
- **Role membership**: a review-scoped role per user (see Step 4), not global.
- **Review**(id, review_id_str, title, owner_id, status, created)
- **Document**(id, review_id, name) with **DocumentVersion**(id, document_id,
  ordinal, content, content_hash, is_baseline, is_final, created_by, created) —
  the immutable baseline replaces the git freeze SHA.
- **ReviewerCopy**(id, review_id, user_id, based_on_version_id, content,
  submitted_at) — one per (review, reviewer); replaces `reviewers/<name>.md`.
- **RID**(id, review_id, rid_str stable, reviewer_id, anchor_json, kind, type,
  severity, status, comment, reply, disposition, resolution, master_id,
  verified_by, verified_on, ai_drafted) — mirrors the frozen v0 RID schema.
- **RidChange**(id, rid_id, version_id, note) — links an implementation edit to
  the RIDs it resolves; replaces "RID id in the commit message".
- **AuditLog**(id, actor_id, action, target, detail_json, ts) — every
  state-changing action; the traceability spine.

## Tasks

1. Write both ADRs. `0001` states plainly: git removed; freeze becomes an
   immutable `DocumentVersion`; RID traceability becomes `RidChange` +
   `AuditLog`; `rtd.yaml` demoted to import/export.
2. Define SQLModel tables + a v0↔DB mapping doc (so `rtd.yaml` import/export is
   lossless for the RID fields).
3. Wire Alembic; generate the initial migration; a `create-all` for tests.
4. Keep the existing domain enums/logic as the source of truth for status/type
   values (DB columns store their `.value`).

## Definition of Done

Migrations apply on a fresh SQLite file; a review with versions, copies, RIDs,
changes and audit rows can be created and queried; `rtd.yaml` for a review can
be produced from the DB and re-imported identically; suite green.

## Out of scope

Any HTTP, auth, or UI (later steps). No behavioural change to triage/lifecycle
logic — only where its data comes from (Step 2).

## Sources

v1 design session 2026-07-09. AI-billing note: Anthropic separates programmatic
Claude Code usage (claude -p / Agent SDK) from the interactive subscription pool
as of 2026-06-15 — recorded in ADR 0001 to justify the interactive-MCP AI design
in Step 7.
