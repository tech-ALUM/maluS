# maluS v1.10 — Admin Superuser Over Every Review

Requested by Alberto Boffi, 2026-07-16 (this repo, Claude Code). A global admin
gets **full permission on every review** — dispose, verify/reopen, implement,
finalize, freeze, apply-suggs, manage members, delete review, delete any
comment, and re-open a reviewer's submission — regardless of membership.

## What changes vs today

Today `is_admin` is *"user management only; no power over review content"*
(`db/models.py`, `api/authz.py`), with two exceptions already granted:
delete-review (v1.5) and manage-members. v1.10 makes admin a **superuser**: it
passes every review-scoped authorization guard.

## Invariant amendment (explicit)

maluS's core invariant is *"closure authority belongs to reviewers, never the
owner."* Alberto chose (2026-07-16) that the admin superuser **may also
verify/reopen** (close) RIDs. The invariant is hereby scoped: **closure is
reviewers + moderators + a global admin; never the owner, never an AI.** The
`is_ai` guard remains absolute — an AI principal never closes or commits, even if
flagged admin (admins are humans). The `CLAUDE.md` invariant line should be
updated to note the admin exception.

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-admin-superuser.md` | admin short-circuits the authz guards; delete-any-comment; re-open submission; GUI controls | v1 (authz), v1.8 (retract), v1.6 (submission panel) |

## Global Definition of Done

- `python -m pytest -q` green; **no schema change / no migration**.
- An admin (with no membership on a review) can dispose / verify / reopen /
  implement / finalize / freeze / apply-suggs / retract any comment / re-open any
  submission / manage members / delete the review.
- The `is_ai` guard still blocks verify/close/commit even for an admin principal.
- Non-admin authorization is unchanged (owner/reviewer/moderator restrictions and
  the "owner never closes" rule still hold for non-admins).

## Sources

- Design session with Alberto Boffi, 2026-07-16 (this repo, Claude Code):
  admin = full permission on everything, on every review, incl. closure.
- Guards in `src/malus/api/authz.py`; existing admin exceptions in
  `src/malus/web/{accounts.py,router.py}`.
