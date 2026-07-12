# maluS v1.3 — Admin Hard-Delete of User Accounts

Requested by Alberto Boffi, 2026-07-12. Today an admin can only **deactivate**
a user (`is_active=False`; blocks login, preserves the account and everything
attributed to it — Step 10). v1.3 adds a true **hard delete** (erasure) of a
user account from the admin GUI, with reassignment/anonymization so referential
integrity and the review/audit history stay intact.

## Why this is not a plain `DELETE`

A `User` is referenced across the model, including **NOT NULL** foreign keys:
`Review.owner_id`, `RID.reviewer_id`, plus `RID.verified_by_id`,
`DocumentVersion.created_by_id`, `AuditLog.actor_id`, `ReviewMember.user_id`,
`ReviewerCopy.user_id` (`src/malus/db/models.py`). A raw delete would violate
FKs or orphan reviews. So a delete must **reassign** every reference before
removing the row.

## What changes vs v1.2

| Concern | v1.2 | v1.3 |
|---|---|---|
| Remove a user | deactivate only (soft) | + hard delete (erasure) from the admin GUI |
| Owned reviews | — | admin picks a new owner per owned review at delete time |
| Historical attributions (findings, verifications, versions, audit) | tied to the user | reassigned to a shared **"Deleted user"** sentinel (records preserved, identity erased) |
| Memberships / raw reviewer copies | tied to the user | deleted |

Deactivate stays as the reversible option; delete is the irreversible erasure.

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-admin-delete-user.md` | Sentinel account; `delete_user` service; confirm + execute GUI (new-owner pickers); guards; anonymization | v1.1.0 Step 10, v1.2 |

## Global Definition of Done

- `python -m pytest -q` green.
- No new runtime dependency; no Alembic migration (data-only; no schema change).
- Referential integrity preserved: after a delete, no dangling FK to the removed
  user; review/audit history intact with the sentinel in place.

## Sources

- Design session with Alberto Boffi, 2026-07-12 (this repo, Claude Code):
  full hard-delete with anonymization; admin picks a new owner per owned review;
  audit entries preserved with the actor anonymized to a shared sentinel.
- Builds on `docs/plan/v1/10-account-gui.md` (deactivate/reactivate) and
  `docs/plan/v1.2/` (member management).
- Model verified against `src/malus/db/models.py`,
  `src/malus/web/accounts.py`, `src/malus/auth/service.py`.
