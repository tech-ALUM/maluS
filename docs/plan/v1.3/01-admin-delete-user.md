# Step 1 — Admin Hard-Delete of a User (with anonymization)

## Objective

Let an admin permanently delete a user account from the GUI. Every reference to
the user is reassigned first — owned reviews to an admin-chosen new owner,
everything else to a shared **"Deleted user"** sentinel — then the row is
removed, with no dangling foreign keys and the review/audit history intact.

## Deliverables

- [x] **Sentinel account**: a singleton `User` with reserved username
      `deleted-user`, display name "Deleted user", `is_active=False`, no password
      (can never log in), `is_ai=False`. Created lazily on the first deletion.
      Hidden from the admin users list; already excluded from the reviewer picker
      (it is inactive) and **not itself deletable**.
- [x] **`delete_user` service** (transactional): reassign `Review.owner_id` (for
      reviews the target primary-owns) to the admin-chosen new owner and ensure
      that owner holds an owner `ReviewMember`; reassign `RID.reviewer_id`,
      `RID.verified_by_id`, `DocumentVersion.created_by_id`, `AuditLog.actor_id`
      from the target to the sentinel; delete the target's `ReviewMember` and
      `ReviewerCopy` rows; delete the `User`; write a `delete_user` audit entry
      (actor = the admin).
- [x] **Confirm page** `GET /ui/admin/users/{username}/delete` (admin-gated):
      lists the reviews the target primary-owns, each with a **new-owner picker**
      (active accounts except the target and the sentinel), summarizes what will
      be anonymized, and requires an explicit confirm.
- [x] **Execute** `POST /ui/admin/users/{username}/delete`: reads a
      `owner_for_<review_id>` per owned review, validates, runs `delete_user`,
      redirects to the users list.
- [x] **Delete control** in `admin_users.html` per user, except the current admin
      (self) and the sentinel.
- [x] **Guards (server-side)**: admin-only (403 otherwise); cannot delete
      yourself (409); the sentinel is not deletable (409); every primary-owned
      review must be given a valid new owner — existing, active, not the target —
      else 422 and nothing is deleted.
- [x] **Tests**: delete an unused user; delete a user who authored a RID (RID
      preserved, `reviewer` becomes "Deleted user"); `verified_by` /
      `created_by` / audit `actor` reassigned to the sentinel (service-level);
      owned-review delete applies the chosen owner; missing/invalid new owner →
      422 (no deletion); self-delete → 409; sentinel not deletable; memberships +
      copies removed; sentinel hidden from the list; admin-gated (403).

## Key behaviors

- **Deactivate is unchanged** and remains the reversible option; delete is the
  irreversible erasure. Both live in the admin area.
- A single shared sentinel means every deleted person collapses to "Deleted
  user" in the RTD/audit — the person is erased, the records are kept.
- The new owner is made a first-class owner (`owner_id` + owner `ReviewMember`),
  so the review stays fully operable after the deletion.
- Reassigning a still-open RID's `reviewer` to the (login-less) sentinel means
  only a moderator can later verify it on the reviewer's behalf — acceptable for
  a departed reviewer.

## Definition of Done

An admin deletes a user in the browser: reviews they owned get the chosen new
owner, their findings/verifications/versions/audit show "Deleted user", their
memberships and copies are gone, and the account no longer exists or logs in; an
owned review without a chosen new owner is refused (422); self-delete and
sentinel-delete are refused; a non-admin is refused (403); suite green.

## Out of scope

- Self-service account deletion (admin-only here).
- Bulk deletion; scheduled/retained-then-purged erasure.
- Per-deleted-user tombstones (a single shared sentinel is used by decision).
- Undo/restore of a hard delete (deactivate is the reversible path).

## Deviations

Recorded in `memory/decisions/2026-07-12-v1.3-step-01-admin-delete-user.md`.

- **Sentinel + service** live in `services/core.py`: `SENTINEL_USERNAME =
  "deleted-user"`, `sentinel_user()` (lazy get-or-create), and `delete_user()`
  (re-exported via `malus.services`). A single shared sentinel, per decision.
- **New-owner picker is keyed by `review_id_str`** in the form
  (`owner_for_<review_id_str>`); the POST handler is `async` and reads the
  dynamic fields via `await request.form()`. Candidates + validation exclude the
  target and the sentinel; an owned review without a valid new owner → 422.
- **`delete_user` reassigns** `RID.reviewer_id`, `RID.verified_by_id`,
  `DocumentVersion.created_by_id`, `AuditLog.actor_id` → sentinel; **deletes**
  the target's `ReviewMember` + `ReviewerCopy` rows; records a `delete_user`
  audit entry (actor = the admin, resolved before the row is removed).
- **`users_page` hides the sentinel** (`username != SENTINEL_USERNAME`);
  `admin_users.html` shows a Delete link on every row except the current admin.
- Service-level reassignment matrix tested in `tests/db/test_delete_user.py`;
  GUI guards + end-to-end anonymization in `tests/web/test_admin_delete.py`.
  No JavaScript added; no Alembic migration (data only).

## Sources

- Design session with Alberto Boffi, 2026-07-12 (approved: full hard-delete,
  admin picks a new owner per owned review, audit preserved+anonymized, shared
  sentinel).
- Current behaviour: `src/malus/web/accounts.py` (admin user CRUD:
  deactivate/activate/reset), `src/malus/auth/service.py`
  (`create_user`/`bootstrap_admin`), `src/malus/db/models.py` (the FK map),
  `src/malus/repo/repositories.py`.
