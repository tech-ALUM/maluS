# Step 4 — RTD GUI

## Objective

The single-file `gui/rtd.html`: the human interface to `rtd.yaml` for
disposition and verification. Opens by double-click in any modern browser;
zero install, zero network, zero paid software.

## Deliverables

- [x] `gui/rtd.html` — complete, self-contained (YAML lib vendored inline)
- [x] Load/save `rtd.yaml` via File System Access API; download-file
      fallback for browsers without it
- [x] Table view: sort + filter by status/reviewer/type/severity/disposition
- [x] Detail pane: full comment, threaded reply, disposition + resolution editing
- [x] Status transitions enforced client-side from the same transition table
      as `constants.py` (generated constant block — single source of truth)
- [x] Role switch: Owner mode (edit reply/disposition/resolution) vs
      Reviewer mode (verify/close own RIDs only) — the GUI enforces the
      closure-authority invariant
- [x] Header dashboard: counts by status/severity, completion %

## Key behaviors

- No build step; plain HTML+CSS+JS in one file. Vendored js-yaml (or a
  minimal YAML subset writer that guarantees round-trip of our schema).
- Never reorders or rewrites untouched YAML fields; regenerating must
  produce minimal diffs (git-friendly saves).
- Works from `file://` — no fetch of local files (user picks rtd.yaml via
  file picker), no external resources.
- Defensive: schema-version check against `meta`, refuse to save on
  validation errors, unsaved-changes guard.

## Definition of Done

Full disposition pass on the step-2 fixture rtd.yaml done entirely in the
GUI in both roles; saved file passes `malus report` validation and shows a
minimal git diff; manual test checklist in `docs/spec/gui-test-checklist.md`.

## Deviations

Implementation choices (settled while building; candidates for `memory/decisions/`):

- **YAML handling:** used the plan's allowed alternative — a targeted reader +
  surgical writer for our schema — instead of vendoring js-yaml. It rewrites only
  edited field lines, so untouched YAML stays byte-identical (minimal diffs). This
  relies on every value being on one line, enabled by the `models.to_yaml`
  single-line/`width` tweak.
- **"Threaded reply"** is the single `reply` field (the frozen RID schema has one
  reply); there is no multi-level threading.
- **Generated constants:** the transition table + enums are spliced into
  `gui/rtd.html` by `python -m malus.gui_constants`; `tests/test_gui.py` fails if
  the block drifts from `constants.py`.
- **`malus report` validation** (DoD) is deferred to Step 5; the GUI-saved file is
  validated with `RTD.from_yaml` in the interim (see the checklist).
- **Verification:** automated Python (self-contained + constants sync) plus the
  in-page `window.__malusSelfTest()` and a full both-role disposition pass on the
  step-2 fixture, both driven in a headless browser; manual checks in
  `docs/spec/gui-test-checklist.md`. Local preview uses a gitignored
  `.claude/launch.json` (`http.server`); the GUI itself needs no server (`file://`).

## Out of scope

Serving over HTTP, multi-user simultaneous editing (single-writer-per-phase
by design), styling beyond clean usable defaults.

## Sources

Design session 2026-07-03 — YAML canonical store + generated/interactive
view decision (`memory/decisions/…`, D2/D3).
