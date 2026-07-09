# Step 1 — Foundations

## Objective

Fix the formal specifications (comment syntax, RID schema, status lifecycle,
review folder layout) and scaffold the Python package with a stub CLI, so
every later step builds on frozen contracts.

## Deliverables

- [x] `docs/spec/comment-syntax.md` — normative comment block grammar
- [x] `docs/spec/rid-schema.md` — normative RID/rtd.yaml schema + lifecycle
- [x] `src/malus/` package: `models.py`, `constants.py`, `cli.py`
- [x] `pyproject.toml` (PEP 621, entry point `malus = malus.cli:app`)
- [x] pytest setup + model unit tests
- [x] All CLI subcommands present as stubs with `--help` text

## Specifications to write (normative content)

### Comment syntax
- `{COMM|type=<t>|sev=<s>: free text}` — discussion comment.
  `type ∈ {typo, editorial, technical, process}` (default `editorial`; the fourth
  type — `process` vs `question` — is an open question to settle here),
  `sev ∈ {minor, major, critical}` (default `minor`). Multi-line allowed;
  literal `}` escaped as `\}`.
- `{SUGG: "exact old text" -> "new text"}` — mechanical replacement
  suggestion, batch-appliable without discussion.
- Blocks may appear anywhere between words/lines of the DUR copy;
  they are the ONLY permitted modification to a reviewer copy (freeze rule).

### RID schema (`rtd.yaml`: `meta:` header + `rids:` list)
```yaml
meta: {review_id, document, baseline_sha, created, owner, reviewers: []}
rids:
  - rid: SIN-SRS-0042          # <PROJECT>-<DOC>-<NNNN>, stable across re-harvests
    reviewer: F. Miccoli
    created: 2026-07-03
    anchor: {section: "3.2.1", quote: "…", line_hint: 142}
    kind: COMM                  # COMM | SUGG
    type: technical             # typo|editorial|technical|process
    severity: major             # minor|major|critical
    status: open
    comment: >-
      …
    reply: null
    disposition: null           # accepted|rejected|deferred
    resolution: null            # what was done; commit refs
    master: null                # RID id if clustered as duplicate
    duplicates: []
    verified_by: null
    verified_on: null
```

### Status lifecycle
`open → answered → implemented → verified`, plus `withdrawn` (from open,
by its reviewer only). Rejected/deferred RIDs skip `implemented`
(`answered → verified`, verification = reviewer acknowledges disposition).
Transition rules are data (`constants.py`), enforced by CLI and GUI alike.
**Invariant: only the reviewer (or moderator on their behalf) may set
`verified` — never the owner.**

### Review instance layout
`reviews/<review-id>/{baseline.md, reviewers/<name>.md, rtd.yaml, report.md}`

## Tasks

1. Write both spec documents (they are contracts; be precise about grammar,
   escaping, defaults, ID stability).
2. Implement dataclasses/enums in `models.py` + YAML round-trip helpers.
3. Typer app in `cli.py` with stub subcommands: `init`, `freeze`, `copies`,
   `harvest`, `triage`, `apply-suggs`, `report`, `verify`, `finalize`, `ai`.
4. Unit tests: model construction, YAML round-trip, transition validation.

## Definition of Done

- Specs reviewed against `memory/specs/` notes (no contradiction).
- `pip install -e .` succeeds; `malus --help` lists all subcommands.
- `python -m pytest -q` green.

## Deviations

Decisions settled during Step 1 (also cited in the `docs/spec/` Sources;
candidates for `memory/decisions/`):

- **Fourth `{COMM}` type = `process`** (not `question`). Settled with
  Alberto Boffi 2026-07-09; resolves the open question in
  `memory/specs/comment-syntax.md`.
- **`{SUGG}` stays mechanical-only** — no rationale parameter; a reviewer who
  needs to justify a change attaches a neighbouring `{COMM}`. Settled 2026-07-09.

Deliberate scoping and spec completions (no behavioural conflict with the plan):

- **Transition enforcement scope.** `transition()` enforces the status graph
  plus the closure-authority invariant. Disposition-conditional routing
  (`accepted → implemented`; `{rejected, deferred} → verified`), the
  traceability rule, and finalize gating are documented as normative in
  `docs/spec/rid-schema.md` but enforced in Step 5 (lifecycle).
- **SUGG payload field.** The frozen RID schema lists no dedicated `old`/`new`
  field for a `{SUGG}`; implemented verbatim (the `comment` field renders the
  change). Whether to add explicit fields is flagged for Step 2.
- **Escaping.** Beyond memory's `\}` rule, the normative spec adds `\"` inside
  `{SUGG}` operands and an "otherwise-literal backslash" rule; flagged as a
  candidate `memory/decisions/` note.
- **Packaging.** Version pinned to `0.0.1` pre-release (the plan sets `0.1.0`
  at Step 7); editable install verified inside a local `.venv`.

## Out of scope

Parsing reviewer copies (step 2), any GUI (step 4), any AI (step 6).

## Sources

Design session 2026-07-03 (Claude chat) — see
`memory/decisions/2026-07-03-architecture-decisions.md`.
