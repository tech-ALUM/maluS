# Step 1 — Member Management from the GUI (picker, roles, removal)

## Objective

Let an owner (or admin) manage a review's members from the Members page over
**real accounts**: add via a searchable picker, change a role inline, and remove
a member — without ever creating placeholder users and without leaving a review
ownerless.

## Deliverables

- [ ] **Account search endpoint** (`GET /ui/accounts/search?q=`) returning an
      HTML fragment of matching **active** accounts (case-insensitive match on
      `display_name` / `username`), owner/admin-gated; consumed by an HTMX
      typeahead on the Members page. Accounts already assigned to the review are
      **excluded** from results — an existing member's role is changed inline in
      the member list, not via the picker.
- [ ] **Add-member submits a `username`** (stable identity), not a free-text
      display name; the server resolves it to an existing user and **rejects an
      unknown or inactive username (422)**. `get_or_create` is removed from this
      path — no more phantom users.
- [ ] **Inline role change** on each member row (owner / reviewer / moderator),
      reusing `ReviewRepo.set_member_role`.
- [ ] **Remove member** action + a new `ReviewRepo.remove_member`
      (`POST /ui/reviews/{id}/members/{username}/remove`; POST for no-JS
      friendliness, HTMX-enhanced).
- [ ] **Owner-safety guard (server-side, 409):** the primary owner
      (`Review.owner_id`) cannot be demoted or removed; any demotion/removal that
      would leave **zero** `ReviewMember(role="owner")` rows is refused. Removing
      a member does **not** delete their RIDs or reviewer copy — access is
      revoked; the data persists, still attributed to them.
- [ ] **Tests:** search returns only active accounts; assign by username;
      unknown/inactive username rejected (no placeholder created); inline role
      change persists; remove works; primary-owner demote/remove refused (409); a
      removed reviewer's harvested RIDs still exist afterwards.

## Key behaviors

- Member management stays **owner-or-admin** (`_can_manage_members`,
  `src/malus/web/accounts.py`); the picker and every new route sit behind the
  same guard.
- Account **creation** remains admin-only in `/ui/admin/users`; the Members page
  only **assigns existing** accounts. If a needed person has no account, an admin
  creates it first — this matches today's effective behaviour, since a
  placeholder user could never log in anyway.
- The picker submits `username`, so identity is the account, not the typed
  string; this removes the typo → phantom-user failure mode at its root.
- AI-reviewer accounts are assigned here as `reviewer` like any account; the
  `is_ai` flag continues to forbid verify/close regardless of role.

## Definition of Done

An owner adds a reviewer by searching existing accounts, changes a member's role
inline, and removes a member — all in the browser; an unknown username is
rejected with no placeholder created; the primary owner cannot be
demoted/removed; a removed member's contributed RIDs remain; suite green.

## Out of scope

- Ownership **transfer** (reassigning `Review.owner_id` to another user).
- Creating brand-new accounts from the Members page (stays in the admin area).
- Bulk member import (use `malus import` / the API).

## Deviations

_None yet — recorded here and in `memory/decisions/2026-07-11-...` as they
arise during implementation._

## Sources

- Design session with Alberto Boffi, 2026-07-11.
- Current behaviour: `src/malus/web/accounts.py` (members page/route,
  `get_or_create`), `src/malus/repo/repositories.py`
  (`add_member` / `set_member_role` / `members`; new `remove_member`),
  `src/malus/api/authz.py` (`review_role`), `src/malus/db/models.py`
  (`Review.owner_id`, `ReviewMember`, `User.is_active`),
  `src/malus/services/core.py` (`create_review` seeds `owner_id` + the owner
  member).
