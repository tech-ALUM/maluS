# maluS v1.2 — Member Management & Reviewer Onboarding

Requested by Alberto Boffi, 2026-07-11. Builds on v1.1.0 (Steps 10 & 12): the
browser could already create a review, freeze its baseline, assign per-review
roles, and collect reviewer comments in the in-browser editor. v1.2 closes two
gaps that surfaced in use.

1. **Assigning reviewers is by free-text name.** A typo silently creates an
   unusable placeholder user (`UserRepo.get_or_create`, `src/malus/web/accounts.py`),
   there is no search over existing accounts, no inline role change, and no way
   to remove a member.
2. **No hand-off to reviewers.** Once assigned, a reviewer is not pointed at the
   review; they must know to log in and find it, and "Edit my copy" is one
   button among several. For 10+ reviewers this is fragile ("Ho aggiunto i
   membri e poi?").

## What changes vs v1.1.0

| Concern | v1.1.0 | v1.2 |
|---|---|---|
| Add a member | free-text name → `get_or_create` (phantom users) | searchable picker over existing active accounts; unknown username rejected |
| Change a member's role | re-type the exact display name in the add form | inline role control on the member row |
| Remove a member | not possible | remove action, with an owner-safety guard |
| Reviewer hand-off | none (log in and find it) | shareable review link + reviewer landing CTA + a "to comment" cue in the review list |

Nothing about the review lifecycle, the freeze rule, or the closure invariant
changes. v1.2 is GUI plus a thin service/repo addition (`remove_member`); **no
new runtime dependency**; **no email/SMTP** (deferred, as in Step 10).

## Domain note — the owner is represented twice (do not break this)

An owner exists as **both**:

- `Review.owner_id` — a NOT-NULL FK, the **primary owner**; `review.owner`
  drives disposition/implement audit attribution
  (`src/malus/services/core.py`), and
- a `ReviewMember` row with `role="owner"` — what `authz.review_role` reads for
  RBAC (`src/malus/api/authz.py`).

`create_review` seeds **both** for the creator (`src/malus/services/core.py`).
v1.2 member edits touch **only** `ReviewMember`; the primary owner (`owner_id`)
is protected from demotion/removal (see Step 1). Ownership **transfer**
(reassigning `owner_id`) is out of scope for v1.2.

## Steps

| # | File | Scope | Depends on |
|---|---|---|---|
| 1 | `01-member-management.md` | Searchable account picker; assign by real identity; inline role change; remove member; owner-safety guard | v1.1.0 Step 10 |
| 2 | `02-reviewer-onboarding.md` | Shareable review link; reviewer landing CTA; "to comment" cue in the review list | v1.1.0 Steps 5–6, 10 |

Steps 1 and 2 map to the design workstreams as: Step 1 = picker + member
management (workstreams A + B, merged — same Members page/route and shared
tests); Step 2 = the reviewer hand-off (workstream C). Implemented one step at a
time, in order, per `CLAUDE.md`. Per-step decisions are recorded in
`memory/decisions/` as each step is built.

## Global Definition of Done

- `python -m pytest -q` green at the end of every step.
- No new runtime dependency; no secret committed; assets vendored (no runtime CDN).
- Closure invariant and freeze rule unchanged and still enforced server-side.
- Each deviation recorded in the step file and, if architectural, in
  `memory/decisions/`.

## Sources

- Design session with Alberto Boffi, 2026-07-11 (this repo, Claude Code):
  problem framing ("does each reviewer upload their MD?" → no, since the v1 web
  pivot), scope decision ("Aggancio + picker"), the added requirement that the
  **owner manage members and roles** (add / change / remove), and the no-email
  default.
- Builds on `docs/plan/v1/10-account-gui.md` (per-review role assignment) and
  `docs/plan/v1/12-gui-review-creation.md` (create + freeze in the GUI).
- Current behaviour verified against `src/malus/web/accounts.py`,
  `src/malus/web/router.py`, `src/malus/api/authz.py`,
  `src/malus/db/models.py`, `src/malus/repo/repositories.py`,
  `src/malus/services/core.py`.
