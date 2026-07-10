# Step 12 — GUI: Create Review + Login Feedback

Added post-v1.0.0 (requested by Alberto, 2026-07-10): the browser could log in
and run the review cycle, but a review still had to be created via the API.

## Objective

Make the browser self-sufficient for *starting* a review, and surface login
errors clearly.

## Deliverables

- [ ] "New review" GUI (`/ui/reviews/new`): create a review (creator = owner) and
      set + freeze the baseline in one step; linked from the review list
- [ ] Login shows an error on wrong credentials (works with `hx-boost` too)
- [ ] Tests: create-review-from-GUI (appears in the list, baseline frozen);
      duplicate review id shows an error; login with wrong credentials shows the
      message

## Definition of Done

An owner creates and freezes a review entirely in the browser and it appears in
their list, ready to add reviewers and collect comments; a failed login shows a
clear "invalid credentials" message; suite green.

## Out of scope

Bulk import UI (use `malus import` / the API). Editing review metadata after
creation.

## Sources

Requested by Alberto Boffi, 2026-07-10 (GUI self-sufficiency + login UX).
