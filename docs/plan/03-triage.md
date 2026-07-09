# Step 3 — Triage

## Objective

Reduce reviewer noise before the owner sees the RTD: cluster duplicate
findings under master RIDs and batch-apply mechanical suggestions.

## Deliverables

- [ ] `src/malus/triage.py` — clustering + SUGG application
- [ ] `malus triage` — interactive/auto duplicate clustering
- [ ] `malus apply-suggs` — apply accepted SUGGs to a working copy
- [ ] Tests on fixtures with overlapping comments

## Key behaviors

- **Duplicate candidates**: same/nearby anchor (same section, quote overlap
  or line_hint within a window) + text similarity (difflib ratio ≥ threshold,
  configurable). Candidates are proposed, not silently merged: `--auto`
  accepts proposals ≥ high-confidence threshold, otherwise CLI lists
  proposals for confirmation.
- **Master/duplicate model**: duplicates get `master: <rid>` and status
  follows the master automatically; masters list their `duplicates: []`.
  Every reviewer's authorship remains visible.
- **SUGG handling**: identical SUGGs collapse automatically (pure dedup).
  `malus apply-suggs` applies accepted SUGGs to a working copy of the
  document with a dry-run mode showing a unified diff; each application is
  reported; SUGGs whose "old text" no longer matches are flagged, not guessed.
- Typos/SUGGs never generate discussion-grade workload: default disposition
  proposal for SUGG RIDs is `accepted`.

## Definition of Done

Fixture with 3 reviewers flagging the same issue → one master + 2 linked
duplicates after `malus triage --auto`; `apply-suggs --dry-run` shows correct
diff and real run applies it; suite green.

## Out of scope

AI-assisted semantic clustering (step 6 extends the same interface).

## Sources

Design session 2026-07-03 — dedup/triage step and SUGG/COMM distinction
(`memory/decisions/…`, D4).
