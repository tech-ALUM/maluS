# Step 4 — RTD GUI

## Objective

The single-file `gui/rtd.html`: the human interface to `rtd.yaml` for
disposition and verification. Opens by double-click in any modern browser;
zero install, zero network, zero paid software.

## Deliverables

- [ ] `gui/rtd.html` — complete, self-contained (YAML lib vendored inline)
- [ ] Load/save `rtd.yaml` via File System Access API; download-file
      fallback for browsers without it
- [ ] Table view: sort + filter by status/reviewer/type/severity/disposition
- [ ] Detail pane: full comment, threaded reply, disposition + resolution editing
- [ ] Status transitions enforced client-side from the same transition table
      as `constants.py` (generated constant block — single source of truth)
- [ ] Role switch: Owner mode (edit reply/disposition/resolution) vs
      Reviewer mode (verify/close own RIDs only) — the GUI enforces the
      closure-authority invariant
- [ ] Header dashboard: counts by status/severity, completion %

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

## Out of scope

Serving over HTTP, multi-user simultaneous editing (single-writer-per-phase
by design), styling beyond clean usable defaults.

## Sources

Design session 2026-07-03 — YAML canonical store + generated/interactive
view decision (`memory/decisions/…`, D2/D3).
