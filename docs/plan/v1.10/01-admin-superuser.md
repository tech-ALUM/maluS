# Step 1 — Admin superuser over every review

## Objective

Give a global admin full authority on every review by short-circuiting the
review-scoped authorization guards, plus two new admin capabilities (delete any
comment, re-open any submission) and the GUI controls to use them. Keep the
`is_ai` guard absolute.

## Deliverables

- [x] **authz** (`api/authz.py`): a global admin passes every review guard,
      regardless of membership — `require_owner`, `require_moderator`,
      `require_owner_or_moderator` return early for `is_admin`;
      `require_verify` returns `True` (moderator-style, on-behalf) for `is_admin`,
      **after** the `is_ai` block so an AI-admin is still refused. `require_own_copy`
      is unchanged (admin moderates copies; it does not author comments as a
      reviewer). `forbid_ai_commit` unchanged.
- [x] **Delete any comment**: the retract route (`web/router.py`) allows an admin
      to retract **any** reviewer's comment at **any** status (non-admins stay
      own-comment + OPEN-only). Reuses `retract_comment` (pristine → hard-delete,
      acted-upon → withdrawn — history preserved even for admin).
- [x] **Re-open submission** (new): `reopen_submission` service
      (`services/core.py`) sets a reviewer copy's `submitted_at` back to `None`
      (draft); route `POST /ui/reviews/{id}/reopen-submission/{reviewer}`
      (admin-only); a **"re-open"** control in the dashboard submissions panel on
      each *submitted* reviewer (admin only).
- [x] **GUI controls for admin**: the finding page shows the dispose form and the
      verify/reopen controls to an admin (`can_dispose` / `can_verify` include
      `user.is_admin and not user.is_ai`); the implement action and the RTD-table
      retract control show for admin; discard-draft allows admin.
- [x] **Tests**: an admin with **no membership** can dispose, verify, reopen,
      implement, finalize, freeze, apply-suggs on a review; admin retracts another
      reviewer's comment; admin re-opens a submission (`submitted_at` → null); an
      `is_ai` admin is still refused verify/commit; non-admin restrictions are
      unchanged (reviewer can't dispose, owner still can't verify).

## Key behaviors

- Admin authority is membership-independent: guards short-circuit on `is_admin`,
  so an admin never needs to be a member of a review to act on it.
- The one hard limit is `is_ai`: an AI principal never closes/commits, admin or
  not (checked before the admin short-circuit in `require_verify`, and in
  `forbid_ai_commit` / the service guards).
- Admin "delete comment" reuses the retraction model: a pristine comment is
  hard-deleted, one the owner already acted on becomes `withdrawn` (its history is
  not erased, even for an admin).

## Definition of Done

An admin does everything on any review without being a member, including
verify/reopen; an AI principal is still blocked from closure/commit; non-admin
authorization is unchanged; suite green; no migration.

## Out of scope

- Admin authoring comments as a reviewer (impersonation) — admin moderates, does
  not write another user's copy.
- Hard-erasing a disposed/verified finding (admin retract still keeps history as
  `withdrawn`).
- Owner/moderator gaining the re-open-submission control (admin-only for now).

## Deviations

- Amends the closure invariant: closure is now reviewers + moderators + admin,
  never the owner, never an AI (see overview). The `CLAUDE.md` invariant line
  should be updated to reflect the admin exception. (Project knowledge base is now
  OpenBrain; no in-repo `memory/decisions/` note.)

## Sources

- Design session with Alberto Boffi, 2026-07-16 (this repo, Claude Code).
- `src/malus/api/authz.py` (guards), `src/malus/web/router.py` (retract, finding,
  submissions), `src/malus/services/core.py` (retract_comment, new
  reopen_submission), `templates/{finding,review}.html`.
