# Step 1 — Foundations

## Objective

Fix the formal specifications (comment syntax, RID schema, status lifecycle,
review folder layout) and scaffold the Python package with a stub CLI, so
every later step builds on frozen contracts.

## Deliverables

- [ ] `docs/spec/comment-syntax.md` — normative comment block grammar
- [ ] `docs/spec/rid-schema.md` — normative RID/rtd.yaml schema + lifecycle
- [ ] `src/malus/` package: `models.py`, `constants.py`, `cli.py`
- [ ] `pyproject.toml` (PEP 621, entry point `malus = malus.cli:app`)
- [ ] pytest setup + model unit tests
- [ ] All CLI subcommands present as stubs with `--help` text

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

## Out of scope

Parsing reviewer copies (step 2), any GUI (step 4), any AI (step 6).

## Sources

Design session 2026-07-03 (Claude chat) — see
`memory/decisions/2026-07-03-architecture-decisions.md`.
