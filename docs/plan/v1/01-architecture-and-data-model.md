# Step 1 — Architecture & Data Model

## Objective

Record the v1 architecture as an ADR, define the database schema, and map the
existing domain models onto it — before any web code is written.

## Deliverables

- [x] `docs/adr/0001-v1-web-pivot.md` — the decision to drop git, adopt a
      DB + web app, and the AI-billing constraint (see Sources)
- [x] `docs/adr/0002-stack.md` — FastAPI + SQLModel/SQLite(→Postgres) + Alembic
      + argon2 auth + MCP; rationale and rejected alternatives
- [x] `src/malus/db/` — SQLModel table definitions + engine/session setup
- [x] Alembic configured; initial migration
- [x] `docs/spec/data-model.md` — normative schema + how each v0 concept maps
- [x] Tests: models create, relationships, constraints, enum round-trips

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

## Deviations

Agreed with Alberto before coding; details in
`memory/decisions/2026-07-10-v1-step-01-decisions.md`.

- **Repo location.** The v1 plan lived in the planning workspace; the code repo
  was relocated to `~/Documents/ALUM/maluS` (the plan's home) instead of copying
  the plan into the old `~/Documents/ALUM/code/maluS`.
- **Schema, made concrete beyond the outline (approved):**
  - "Role membership" is a concrete `review_members` table (schema only; RBAC
    enforcement is Step 4).
  - `users.display_name` added — reproduces the exact `rtd.yaml` name strings for
    a lossless round-trip; `owner`/`reviewer`/`verified_by`/`created_by` are User
    FKs (`*_id`), rendered back to names on export.
  - `reviews.rid_prefix` added so `meta.rid_prefix` round-trips (else derived).
  - `meta.baseline_sha` maps to the baseline `document_versions.content_hash`;
    for a v0 import (no content) the original SHA is preserved verbatim.
  - `duplicates` is **not** a column — it is derived from the `master_id` inverse.
  - Enum columns are plain `str` holding `.value` (not SQL `Enum` types); the
    mapping layer converts. `reviews.status` uses a provisional `ReviewStatus`
    enum (draft/active/finalized) defined in `db/`, not in the frozen
    `constants`; the full review lifecycle is refined later.
  - Table `users` (not `user`) to avoid the PostgreSQL reserved word.
- **Tests** live in `tests/db/test_db_*.py` (the `db_` prefix avoids a pytest
  module-name clash with the existing `tests/test_models.py`).
- **`docs/usage.md`** was already showing as deleted in the working tree at the
  start of the session; left untouched (out of Step-1 scope).

## Sources

v1 design session 2026-07-09. AI-billing note: Anthropic separates programmatic
Claude Code usage (claude -p / Agent SDK) from the interactive subscription pool
as of 2026-06-15 — recorded in ADR 0001 to justify the interactive-MCP AI design
in Step 7.
