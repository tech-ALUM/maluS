# Step 1 — Linear freeze validation & offset mapping (perf fix)

## Objective

Make Save draft / Submit copy fast. Replace the two character-level
`difflib.SequenceMatcher` passes in the harvest core with one linear
two-pointer alignment that validates the freeze rule **and** produces the
residue→baseline offset map in a single O(n) pass. No public-signature or
server-contract change.

## Root cause (verified)

- `validate_insertion_only` diffs baseline vs residue char-by-char
  (`src/malus/harvest.py:73`).
- `_build_r2b` runs a second char-level diff per copy
  (`src/malus/harvest.py:91`).
- `POST /ui/reviews/{id}/edit-copy` runs the validation once as pre-check,
  then `svc.harvest → build_rtd` re-validates and re-maps **every** copy
  (`src/malus/web/router.py:468-485`, `src/malus/harvest.py:174-186`).
- Net: `1 + 2·N_copies` O(n²)-ish diffs of the whole document per click.

## Semantics (normative for the new matcher)

The freeze rule accepts a residue that differs from the baseline **only in
whitespace**. Formally: `strip_ws(baseline) == strip_ws(residue)` where
`strip_ws` removes every whitespace character. This is the intent of D1 and
matches the difflib implementation on all non-pathological inputs (the
equivalence tests prove it on generated corpora).

## Files

- Modify: `src/malus/harvest.py` — add `_align_ws`, rewire
  `validate_insertion_only` and `_build_r2b`.
- Test: `tests/test_harvest_perf.py` (new) + existing suite untouched.

## Interfaces

- Produces: `_align_ws(baseline: str, residue: str) -> list[int]` — returns
  `r2b` (length `len(residue)+1`, `r2b[len(residue)] == len(baseline)`), or
  raises `FreezeViolation(msg, line)` at the first non-whitespace mismatch
  (line = 1-based line in **baseline**).
- `validate_insertion_only(baseline, copy)` keeps its exact signature and
  return (`list[ParsedBlock]`), and still raises `ParseError` from `scan`.
- `_build_r2b(baseline, residue)` keeps its signature, now delegating.

## Algorithm

Two pointers `i` (baseline), `j` (residue), building `r2b`:

1. If both chars exist and are equal → `r2b[j] = i`, advance both.
2. Else if `residue[j]` is whitespace → `r2b[j] = i`, `j += 1`.
3. Else if `baseline[i]` is whitespace → `i += 1`.
4. Else → `FreezeViolation` at baseline line `baseline[:i].count("\n") + 1`.

Tail: leftover non-ws on either side → violation; finally
`r2b[len(residue)] = len(baseline)`.

## Deliverables (TDD)

- [x] Failing tests first (`tests/test_harvest_perf.py`):
      equivalence vs the difflib behavior on a generated corpus — documents
      with tables/fences/unicode; ws-only perturbations (accepted); real text
      edits, deletions, reorders (rejected, correct line); block-stripped
      copies from real `{COMM}/{SUGG}` insertions (accepted); plus mapping
      invariants (r2b monotone, equal-char positions map exactly).
- [x] Perf guard test: a ~300 KB baseline with 20 inserted blocks validates +
      maps in < 1.0 s (generous bound; the old code takes far longer).
- [x] Implement `_align_ws`; rewire `validate_insertion_only` / `_build_r2b`;
      delete the two SequenceMatcher usages (import stays only if still used
      elsewhere in the file — it is not).
- [x] Full suite green; commit
      `perf(harvest): linear freeze validation and offset mapping (v2 step 1)`.

## Definition of Done

Suite green including new equivalence + perf tests; no signature change;
`git grep SequenceMatcher src/malus/harvest.py` returns nothing.

## Out of scope

- Caching harvest results / skipping unchanged copies (unnecessary once
  linear).
- Any UI change.

## Sources

- `00-design.md` §3 (approved B1); measured code paths cited above.
