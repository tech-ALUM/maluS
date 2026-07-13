# Step 1 — Delete a Review (owner/admin, from the GUI)

## Objective

Let the primary owner (or a global admin) permanently delete a review and all its
data from the browser, behind an explicit confirmation. Reviewers and moderators
cannot.

## Deliverables

- [ ] **`delete_review` service** (transactional, in `services/core.py`): remove
      the review's children in FK-safe order — `RidChange`, then `RID` (nulling
      the `master_id` self-reference first), `ReviewerCopy`, `ReviewerNote`,
      `ReviewMember`, `DocumentVersion`, `Document` — then the `Review`; write a
      `delete_review` audit entry (actor = the acting owner/admin). Exported via
      `malus.services`.
- [ ] **Confirm page** `GET /ui/reviews/{id}/delete` (owner-or-admin): shows what
      will be permanently removed (findings count, reviewers, document + versions,
      copies + private notes) and a **"Delete permanently"** button.
- [ ] **Execute** `POST /ui/reviews/{id}/delete`: runs `delete_review`, redirects
      to the review list.
- [ ] **"Delete review"** control on the review dashboard, shown only to the
      owner or an admin (danger-styled).
- [ ] **Guards (server-side)**: owner-or-admin only — reviewer/moderator get 403
      on both the confirm page and the execute route.
- [ ] **Tests**: service removes every dependent row (RID, RidChange,
      ReviewerCopy, ReviewerNote, ReviewMember, Document, DocumentVersion) and the
      Review; GUI owner delete → review 404 + gone from the list; admin can
      delete; reviewer/moderator → 403 and no delete control; a `delete_review`
      audit entry exists.

## Key behaviors

- Irreversible hard delete (there is no soft "archive" — YAGNI; the owner chose a
  real delete). `AuditLog` entries stay (append-only; they reference the review by
  string, not FK), preserving "review X was deleted".
- No `DocumentVersion`/`RID` is left orphaned; the `RID.master_id` self-reference
  is cleared before deleting the RIDs so it holds whether or not SQLite FK
  enforcement is on.

## Definition of Done

An owner (or admin) deletes a review in the browser after a confirmation; it 404s
and disappears from the list; every dependent row is gone; a reviewer/moderator is
refused (403) and never sees the control; suite green.

## Out of scope

- Soft delete / archive / restore (this is a hard delete).
- Bulk review deletion.
- Deleting a single document version or RID (separate concerns).

## Deviations

_None yet — recorded here and in `memory/decisions/2026-07-12-v1.5-...` as they
arise during implementation._

## Sources

- Design session with Alberto Boffi, 2026-07-12.
- Mirrors `delete_user` (`docs/plan/v1.3/01-admin-delete-user.md`); model +
  FKs in `src/malus/db/models.py`; owner/admin gate like
  `src/malus/web/accounts.py` `_can_manage_members`.
