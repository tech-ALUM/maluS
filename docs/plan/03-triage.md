# Step 3 — Triage

## Objective

Reduce reviewer noise before the owner sees the RTD: cluster duplicate
findings under master RIDs and batch-apply mechanical suggestions.

## Deliverables

- [x] `src/malus/triage.py` — clustering + SUGG application
- [x] `malus triage` — interactive/auto duplicate clustering
- [x] `malus apply-suggs` — apply accepted SUGGs to a working copy
- [x] Tests on fixtures with overlapping comments

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

## Deviations

Decisions settled with Alberto Boffi 2026-07-09 (candidates for `memory/decisions/`):

- **`apply-suggs` applies every suggestion not explicitly rejected** (default-
  accepted per D4), so batch-apply runs during triage — not only owner-accepted
  ones.
- **`triage` = list + `--auto`**: without `--auto` it lists the proposed groups
  and changes nothing; `--auto` links the high-confidence groups. Interactive
  per-group yes/no prompts were deferred.

Implementation choices:

- **Master selection** = the lowest-numbered RID in a group; **thresholds**
  0.60 to propose a group, 0.82 to auto-accept (adjustable via `--threshold`),
  using a difflib similarity on the normalized comment text within the same
  section.
- **Duplicate status follows the master** at clustering time; ongoing sync when
  the master changes belongs to Step 5.
- **SUGG operand escaping** added to the harvest rendering so the stored comment
  re-parses losslessly (`parse_sugg_comment`), since the RID schema has no
  dedicated `old`/`new` fields.
- **`apply-suggs` writes `<review>/working.md`** from the frozen `baseline.md`
  (the baseline is never modified); `--dry-run` previews a unified diff.

## Out of scope

AI-assisted semantic clustering (step 6 extends the same interface).

## Sources

Design session 2026-07-03 — dedup/triage step and SUGG/COMM distinction
(`memory/decisions/…`, D4).
