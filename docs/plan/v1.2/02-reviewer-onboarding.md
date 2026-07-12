# Step 2 — Reviewer Onboarding & Hand-off

## Objective

After assignment, point a reviewer straight to commenting: a shareable review
link the owner can send, a clear reviewer landing CTA, and a "to comment" cue in
the review list — no email/SMTP.

## Deliverables

- [x] **Copy-link affordance** on the review page (and the Members page): copies
      the review URL (`/ui/reviews/{id}`) to the clipboard via a small inline
      script in the style of `src/malus/web/static/editor.js`, with a visible
      text fallback when the clipboard API is unavailable.
- [x] **Reviewer landing CTA:** when the current user's role is `reviewer`, the
      review page shows a prominent banner + primary CTA ("Add your comments" →
      `/ui/reviews/{id}/edit-copy`), above the existing button row.
- [x] **"To comment" cue** in the review list (`/ui/reviews`): reviews where the
      user is a `reviewer` and has **not yet submitted** their copy are badged
      (e.g. "to comment"); "submitted" = a `ReviewerCopy` row exists for
      (review, user) with `submitted_at` set (`upsert` stamps it,
      `src/malus/repo/repositories.py`).
- [x] **Tests:** a reviewer sees the landing CTA and the list badge; the badge
      clears after the copy is submitted; owner/moderator never see the reviewer
      CTA; the copy-link control is present for the owner.

## Key behaviors

- The shareable link is the existing **authenticated** review URL — no anonymous
  access. The recipient still needs their account and a `reviewer` seat; the
  link only removes "where do I go?", not authentication.
- Nothing changes about who may comment: only a `reviewer` gets the CTA, and
  `edit-copy` stays reviewer-gated (403 otherwise, `src/malus/web/router.py`).
- The list cue reuses the per-row role already computed in `reviews_page`; the
  submitted check is a single lookup on the reviewer's own copy.

## Definition of Done

A reviewer opens the shared link (or the review list), immediately sees a clear
"add your comments" path, comments, and the "to comment" cue disappears once the
copy is submitted; non-reviewers never see the reviewer CTA; suite green.

## Out of scope

- Email or any other push notification (deferred — would add SMTP
  infrastructure; see `docs/plan/v1/10-account-gui.md` out-of-scope).
- Read/seen receipts.
- An owner-facing per-reviewer progress dashboard (who has/hasn't commented).

## Deviations

Recorded in `memory/decisions/2026-07-12-v1.2-step-02-reviewer-onboarding.md`.

- **The reviewer's "Edit my copy" action button was replaced** by the prominent
  landing CTA banner ("Add your comments" → same `edit-copy` page). The banner is
  the hand-off; the duplicate button was removed (no test relied on it).
- **Copy-link is shown to owner or admin** (`role == 'owner' or user.is_admin`),
  matching the Members-button gating. It builds the absolute URL client-side
  from `data-path` + `location.origin` (`malusCopyLink`), with a
  `window.prompt` fallback when `navigator.clipboard` is unavailable.
- **"To comment" cue** is computed in `reviews_page`: `role == reviewer` and no
  submitted copy (no `ReviewerCopy` row, or `submitted_at` is None).

## Sources

- Design session with Alberto Boffi, 2026-07-11 (the "e poi?" hand-off gap).
- Current behaviour: `src/malus/web/router.py` (`reviews_page` lists all reviews
  with a per-user role; `edit_copy` reviewer-gated), `src/malus/web/templates/
  review.html` and `reviews.html` (entry points), `src/malus/db/models.py`
  (`ReviewerCopy.submitted_at`), `src/malus/repo/repositories.py`
  (`ReviewerCopyRepo.upsert` stamps `submitted_at`).
