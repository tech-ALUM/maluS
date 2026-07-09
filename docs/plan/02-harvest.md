# Step 2 — Harvest

## Objective

Turn N reviewer copies into one canonical `rtd.yaml`: validate the freeze
rule, parse comment blocks with their anchors, assign stable RID ids.

## Deliverables

- [x] `src/malus/parser.py` — comment block tokenizer/parser
- [x] `src/malus/harvest.py` — diff-based extraction + rtd.yaml writer
- [x] `malus freeze` — record baseline SHA into review meta
- [x] `malus copies` — generate per-reviewer copies (files or git branches)
- [x] `malus harvest` — working end-to-end on fixtures
- [x] Fixture set under `tests/fixtures/` (baseline + ≥3 reviewer copies,
      including one violating copy)

## Key behaviors

- **Freeze validation**: diff each copy against `baseline.md`. Allowed delta:
  insertions consisting solely of valid comment blocks (plus surrounding
  whitespace). Any other change → harvest fails for that copy with a precise
  report (file, line, offending hunk); other copies still process.
- **Anchoring**: each comment records nearest preceding heading (`section`),
  the immediately preceding sentence/fragment (`quote`, truncated ~120 chars),
  and baseline `line_hint`.
- **Stable IDs**: `rid = <PROJECT>-<DOC>-<NNNN>`; NNNN assigned in document
  order at first harvest. Re-harvest matches existing RIDs by
  (reviewer, content hash) so ids, replies and statuses survive; new comments
  get new ids; vanished comments are marked `withdrawn`, never deleted.
- **Idempotence**: harvest twice with no copy changes → byte-identical rtd.yaml.

## Tasks

1. Grammar-driven parser for `{COMM|…: …}` / `{SUGG: "…" -> "…"}` with
   escaping (`\}`) and multi-line support; precise error positions.
2. Insertion-only diff validation (difflib against baseline).
3. Anchor extraction from insertion positions in the baseline coordinate space.
4. rtd.yaml assembly + stable-id reconciliation with a pre-existing rtd.yaml.
5. Tests: parser unit tests (valid, escaped, malformed), freeze-violation
   detection, anchor correctness, idempotence, re-harvest stability.

## Definition of Done

`malus harvest` on the fixture review produces a correct, idempotent
rtd.yaml; violating copy rejected with actionable message; suite green.

## Deviations

Decisions settled with Alberto Boffi 2026-07-09 (candidates for `memory/decisions/`):

- **File-based reviewer copies** (deviation from D1's git-branch phrasing).
  `copies`/`harvest` operate on `reviews/<id>/reviewers/<name>.md`; git-branch
  mode deferred to a later step.
- **`meta.rid_prefix`** — optional schema field; the `<PROJECT>-<DOC>` prefix is
  `meta.rid_prefix` when set, else `review_id` minus its trailing `-<revision>`
  segment. (Also recorded in `docs/spec/rid-schema.md`.)

Implementation choices (no behavioural conflict):

- **Freeze SHA** = the baseline's git blob SHA (`git hash-object`), deterministic
  without a commit. `freeze` also bootstraps `rtd.yaml` meta when absent, since
  `init` is still a stub.
- **Freeze validation** = strip parsed blocks from the copy; the residue must
  differ from `baseline.md` only in whitespace (char-level `difflib`).
- **YAML aliasing disabled** in `to_yaml` (fix) — required for idempotence and
  clean diffs.
- **`{SUGG}` dedup** credits the first reviewer in document order to a single
  RID; multi-reviewer credit is left to triage (Step 3).
- **Anchor `quote`** = the ~120 preceding characters, whitespace-collapsed; may
  span a heading boundary (a context hint only). Refine if needed later.

## Out of scope

Duplicate clustering (step 3), applying SUGGs (step 3).

## Sources

Design session 2026-07-03 — freeze rule and diff-extraction decision
(`memory/decisions/2026-07-03-architecture-decisions.md`, D1).
