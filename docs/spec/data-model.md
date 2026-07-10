# v1 Data Model — Normative Specification

**Status:** Normative. Introduced at v1 Step 1 (Architecture & Data Model).
The schema is defined in `src/malus/db/models.py` (SQLModel) and versioned by
Alembic (`alembic/versions/`). Changes require a migration and, if
architectural, a recorded decision in `memory/decisions/`.

## 1. Purpose and principles

Per **ADR 0001**, the relational database is the canonical store; git is
removed. Per **ADR 0002** the ORM is SQLModel (SQLAlchemy 2 + Pydantic 2) on
SQLite (WAL, Postgres-ready). `rtd.yaml` survives only as an **import/export
interchange format** (`src/malus/db/rtd_io.py`), no longer the store.

Three principles constrain the schema:

1. **The domain vocabulary is not duplicated.** Enum/status/type values are
   owned by `malus.constants`; columns store the enum **`.value`** string and
   the mapping layer reconstructs the member. (`docs/spec/rid-schema.md` remains
   the normative RID contract.)
2. **Freeze and traceability become data.** The frozen baseline is an immutable
   `DocumentVersion` (content hash) instead of a git commit SHA; RID
   traceability is `RidChange` links + an append-only `AuditLog` instead of RID
   ids in commit messages.
3. **Invariants are enforced server-side** (later steps), never only in the UI.
   The closure-authority invariant (D3) lives in `malus.models.transition` and
   is not forked.

## 2. Entities

Primary keys are integer surrogate `id` columns and are omitted below. Table
names are snake_case plural; `users` is spelled out because `user` is reserved
in PostgreSQL.

### `users`
| Column | Type | Null | Notes |
|--------|------|------|-------|
| `username` | str | no | unique, indexed; login handle (auth at Step 4) |
| `display_name` | str | no | exact name reproduced in `rtd.yaml` (owner/reviewer/verified_by) |
| `email` | str | yes | |
| `password_hash` | str | yes | argon2, set at Step 4; null for import placeholders |
| `is_active` | bool | no | default true |
| `created` | datetime | no | system timestamp |

### `reviews`
| Column | Type | Null | Notes |
|--------|------|------|-------|
| `review_id_str` | str | no | unique, indexed; `rtd.meta.review_id` |
| `title` | str | yes | |
| `rid_prefix` | str | yes | `rtd.meta.rid_prefix`; when null it is derived from `review_id` |
| `owner_id` | FK→users | no | the document owner |
| `status` | str | no | `ReviewStatus.value` (provisional: draft/active/finalized) |
| `created` | date | no | `rtd.meta.created` |

### `review_members`
Review-scoped role for a user (RBAC enforcement arrives at Step 4).
| Column | Type | Null | Notes |
|--------|------|------|-------|
| `review_id` | FK→reviews | no | |
| `user_id` | FK→users | no | |
| `role` | str | no | `Role.value`: owner \| reviewer \| moderator |

Unique `(review_id, user_id)`.

### `documents`
| Column | Type | Null | Notes |
|--------|------|------|-------|
| `review_id` | FK→reviews | no | |
| `name` | str | no | `rtd.meta.document` (name/path of the DUR) |

### `document_versions`
The immutable baseline replaces the git freeze SHA.
| Column | Type | Null | Notes |
|--------|------|------|-------|
| `document_id` | FK→documents | no | |
| `ordinal` | int | no | version order within the document |
| `content` | str | no | the Markdown text (empty for a v0 import with no content) |
| `content_hash` | str | no | immutable baseline identity; sha256(content) for v1-native versions, or the preserved `rtd.meta.baseline_sha` for a v0 import |
| `is_baseline` | bool | no | the frozen baseline |
| `is_final` | bool | no | the finalized document |
| `created_by_id` | FK→users | yes | |
| `created` | datetime | no | |

### `reviewer_copies`
One per (review, reviewer); replaces `reviewers/<name>.md`. The freeze rule
(D1 — reviewers add only comment blocks) is re-validated server-side by the
existing parser in a later step.
| Column | Type | Null | Notes |
|--------|------|------|-------|
| `review_id` | FK→reviews | no | |
| `user_id` | FK→users | no | |
| `based_on_version_id` | FK→document_versions | yes | the version the copy annotates |
| `content` | str | no | the reviewer's annotated Markdown |
| `submitted_at` | datetime | yes | |

Unique `(review_id, user_id)`.

### `rids`
Mirrors the frozen v0 RID schema (`docs/spec/rid-schema.md` §1).
| Column | Type | Null | Notes |
|--------|------|------|-------|
| `review_id` | FK→reviews | no | |
| `rid_str` | str | no | indexed; stable `<PROJECT>-<DOC>-<NNNN>` |
| `reviewer_id` | FK→users | no | the finding's author (`rtd.reviewer`) |
| `created` | date | no | |
| `anchor_json` | JSON | yes | `{section, quote, line_hint}`; members may be null |
| `kind` | str | no | `Kind.value` (COMM \| SUGG) |
| `type` | str | yes | `CommentType.value` or null (null for SUGG) |
| `severity` | str | yes | `Severity.value` or null (null for SUGG) |
| `status` | str | no | `Status.value` |
| `comment` | str | yes | finding text (COMM) or `old -> new` rendering (SUGG) |
| `reply` | str | yes | owner's response |
| `disposition` | str | yes | `Disposition.value` or null |
| `resolution` | str | yes | what was done |
| `master_id` | FK→rids | yes | this RID's master, if clustered as a duplicate |
| `verified_by_id` | FK→users | yes | reviewer/moderator who set `verified` |
| `verified_on` | date | yes | |
| `ai_drafted` | bool | no | reply/disposition awaits human confirmation |

Unique `(review_id, rid_str)`. **`duplicates` is not stored** — it is the
inverse of `master_id` (a RID's duplicates are the RIDs whose `master_id` points
to it) and is recomputed on export.

### `rid_changes`
Links an implementation edit to the RID it resolves; replaces "RID id in the
commit message".
| Column | Type | Null | Notes |
|--------|------|------|-------|
| `rid_id` | FK→rids | no | |
| `version_id` | FK→document_versions | no | the version the edit landed in |
| `note` | str | yes | |

### `audit_logs`
Append-only record of every state-changing action; the traceability spine.
| Column | Type | Null | Notes |
|--------|------|------|-------|
| `actor_id` | FK→users | yes | null for system actions |
| `action` | str | no | e.g. `freeze`, `verify`, `disposition` |
| `target` | str | no | e.g. `rid:SIN-SRS-0042` |
| `detail_json` | JSON | yes | structured action detail |
| `ts` | datetime | no | |

## 3. Relationships

```
users ─1─┈ owns ┈──< reviews ──< documents ──< document_versions
  │                     │  │                          │
  │                     │  └──< review_members        ├──< reviewer_copies >── users
  │                     │                             └──< rid_changes >── rids
  └──< (reviewer / verified_by / created_by / actor) …
reviews ──< rids ──(master_id, self)── rids        rids ──< rid_changes
users ──< audit_logs
```

## 4. How each v0 concept maps

| v0.1.0 (git + files + `rtd.yaml`) | v1 (database) |
|---|---|
| `rtd.yaml` as the store | `rtd.yaml` as import/export only; DB is the store |
| `meta.review_id` / `rid_prefix` | `reviews.review_id_str` / `reviews.rid_prefix` |
| `meta.document` | `documents.name` |
| `meta.baseline_sha` (git SHA) | baseline `document_versions.content_hash` |
| `meta.created` | `reviews.created` |
| `meta.owner` / `meta.reviewers` (names) | `users.display_name` via `review_members` (role owner/reviewer, order preserved) |
| `reviewers/<name>.md` files | `reviewer_copies` rows owned by a user |
| baseline pinned to a commit SHA | `document_versions` with `is_baseline` + `content_hash` |
| RID id referenced in a commit message | `rid_changes` (rid ↔ version) + `audit_logs` |
| a RID's `reviewer` / `verified_by` (names) | `rids.reviewer_id` / `verified_by_id` → `users` |
| a RID's `master` (rid id) | `rids.master_id` (self FK) |
| a RID's `duplicates` (list) | derived from the inverse of `master_id` |
| every other RID field | the identically named `rids` column, storing enum `.value` |

`rtd.yaml` ↔ DB is proven lossless (byte-identical canonical serialization,
both directions) in `tests/db/test_db_mapping.py`.

## 5. Constraints, indexes, migrations

- Unique: `users.username`, `reviews.review_id_str`, `(review_id, rid_str)`,
  `(review_id, user_id)` on both `review_members` and `reviewer_copies`.
- Indexes: `users.username`, `reviews.review_id_str`, `rids.rid_str`.
- SQLite runs with `PRAGMA foreign_keys=ON` (enforced) and WAL for file-based
  databases (`src/malus/db/session.py`).
- The schema is created for production via `alembic upgrade head`; tests use
  `SQLModel.metadata.create_all`. The initial migration is verified to apply on
  a fresh SQLite file and to match the model metadata exactly
  (`tests/db/test_db_migration.py`).

## 6. Out of scope (later steps)

Authentication and password hashing, and RBAC enforcement of the review-scoped
roles (Step 4). The full review-level lifecycle behind `reviews.status`
(freeze → harvest → triage → disposition → … → finalize) is refined by the
API/lifecycle steps; Step 1 stores a provisional value only. No behavioural
change to triage/lifecycle logic — only where its data comes from (Step 2).

## Sources

- `docs/adr/0001-v1-web-pivot.md`, `docs/adr/0002-stack.md` — the pivot and the
  stack this schema realises.
- `docs/plan/v1/01-architecture-and-data-model.md` — Step 1 objective, the
  normative schema outline, and tasks (enums as source of truth; columns store
  `.value`; lossless `rtd.yaml` mapping).
- `docs/spec/rid-schema.md` — the frozen RID field contract the `rids` table
  mirrors.
- `memory/decisions/2026-07-03-architecture-decisions.md` — D1 (freeze rule),
  D2 (single canonical RTD), D3 (reviewer-side closure) preserved by this model.
- `src/malus/db/models.py`, `src/malus/db/rtd_io.py` — the implementation this
  document specifies.
