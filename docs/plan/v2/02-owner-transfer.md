# Step 2 — Owner visible & transferable

## Objective

Show the review owner prominently everywhere, and let the current owner or a
global admin transfer ownership. The transferrer chooses the ex-owner's fate:
**removed from the review** or **demoted to reviewer** (never auto-moderator)
— per Alberto's decision, 2026-07-27.

## Files

- Modify: `src/malus/services/core.py` — new `transfer_ownership`.
- Modify: `src/malus/web/accounts.py` — new
  `POST /ui/reviews/{review_id}/transfer-owner` + context for members page.
- Modify: `src/malus/web/router.py` — reviews list rows gain the owner's
  display name.
- Modify: `src/malus/web/templates/reviews.html` (owner chip),
  `review.html` (owner prominent in header), `members.html`
  (Transfer ownership section).
- Test: `tests/test_transfer_ownership.py` (new).

## Interfaces

- Produces:
  `transfer_ownership(session, review, new_owner: User, old_owner_fate: str, by: User) -> Review`
  where `old_owner_fate ∈ {"remove", "reviewer"}`.
  Raises `PermissionError` (→403) when `by` is neither current owner nor
  admin (or is AI); `ValueError` (→422) when the target is AI, inactive,
  or already the owner, or the fate is invalid.
- Ownership is BOTH `Review.owner_id` AND the `ReviewMember` row with
  `role == "owner"` — the service updates the two atomically (flush, caller
  commits, like every service).

## Behavior

1. Authorize: `by.is_admin` or `review_role(by) == owner`; `forbid` AI actors.
2. Validate target: active human user, not already owner.
3. `review.owner_id = new_owner.id`; the target's membership row is created
   as owner or its role is set to `owner` (whether or not already a member).
4. Ex-owner fate: `remove` → delete their `ReviewMember` row; `reviewer` →
   set their row's role to `reviewer` (from then on they may legitimately
   verify — they are no longer the owner).
5. Audit row `transfer_ownership` with actor, old→new owner and fate.

## Deliverables (TDD)

- [ ] Failing tests: owner can transfer; admin can transfer; reviewer /
      moderator / non-member → 403-equivalent error; AI actor refused; AI or
      inactive target → error; self-transfer → error; fate `remove` deletes
      membership; fate `reviewer` leaves reviewer role; `Review.owner_id` and
      member rows consistent after transfer; audit row written; rtd export's
      `meta.owner` reflects the new owner.
- [ ] Implement service + route + templates.
- [ ] Owner chip in `reviews.html` rows and prominent owner block in
      `review.html` header (uses `review.owner.display_name`).
- [ ] Members page section (owner/admin only): user picker reusing the
      existing members search, fate radio (`remove` / `reviewer`), JS
      `confirm()` before POST, redirect back to members with the new state.
- [ ] Browser check via dev preview: transfer as owner, verify chip/header
      change and ex-owner fate.
- [ ] Suite green; commit
      `feat(review): visible + transferable ownership (v2 step 2)`.

## Definition of Done

Owner is visible in list + dashboard; transfer works for owner and admin
with both fates; every negative case rejected server-side; suite green.

## Out of scope

- Email/notification of the new owner (no SMTP in maluS, deferred since v1.2).
- Transferring to an AI principal (explicitly refused: primary ownership is
  human; the v1.7 AI co-owner seat is unaffected).

## Sources

- `00-design.md` §4; decision table §2 (Alberto, 2026-07-27).
- `src/malus/db/models.py` (Review.owner_id, ReviewMember),
  `src/malus/api/authz.py`, `src/malus/web/accounts.py` (members routes).
