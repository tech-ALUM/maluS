# maluS v1.5 — Delete a Review from the GUI

Requested by Alberto Boffi, 2026-07-12. The owner (or a global admin) can
permanently delete a whole review from the browser — the document, all findings,
reviewer copies, private notes, memberships and versions. Irreversible.

## Why this needs a cascade

A `Review` is the root of a tree: `Document` → `DocumentVersion`, `RID` →
`RidChange`, `ReviewerCopy`, `ReviewerNote`, `ReviewMember` (all keyed by
`review_id` / a child id). The FKs carry no `ON DELETE CASCADE`, so a delete must
remove the children first, in FK-safe order, then the `Review` — a transactional
`delete_review` service, mirroring `delete_user` (v1.3). `AuditLog` has no FK to
`Review` (it references it by string `target`), so audit entries are left in
place as the historical trail.

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-delete-review.md` | `delete_review` service (cascade); owner/admin confirm + execute GUI; guards | v1.3 (delete_user pattern) |

## Global Definition of Done

- `python -m pytest -q` green; no schema change / no migration (pure deletes).
- After a delete: the review 404s, is gone from the list, and no dependent row
  survives; a `delete_review` audit entry is written.
- Only the primary owner or a global admin can delete (reviewer/moderator 403).

## Sources

- Design session with Alberto Boffi, 2026-07-12 (owner/admin delete, confirm
  page + button, audit kept).
- Mirrors `docs/plan/v1.3/01-admin-delete-user.md` (cascade + anonymization
  pattern); model in `src/malus/db/models.py`.
