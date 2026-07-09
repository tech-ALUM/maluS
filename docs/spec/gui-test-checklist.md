# GUI Manual Test Checklist — `gui/rtd.html`

Run by double-clicking `gui/rtd.html` (from `file://`); for the file-picker
path, serve the folder over `localhost` (e.g. `python -m http.server`) since the
File System Access API needs a secure context.

**Automated coverage already in place** (need not be re-done by hand):
`tests/test_gui.py` verifies the file is self-contained (no network) and that the
status-transition block matches `malus.constants`; the in-page
`window.__malusSelfTest()` verifies the YAML reader, the transition rules, the
closure-authority invariant, and minimal-diff saving. These were also exercised in
a headless browser during Step 4, including a full disposition + verification pass
on the step-2 fixture in both roles.

## Load / save
- [ ] Open a `rtd.yaml` via the picker (Chromium/Edge use File System Access; other browsers fall back to a download).
- [ ] The table, dashboard, and filters populate; a "loaded … N RID(s)" banner appears.
- [ ] Editing a field shows the unsaved marker (●); closing the tab warns about unsaved changes.
- [ ] Save writes the file in place (File System Access) or downloads it (fallback); the marker clears.
- [ ] Reopen the saved file — the edits are present, and `git diff` shows **only** the edited fields.

## Table
- [ ] Clicking a column header sorts; clicking again reverses.
- [ ] Each filter (status / reviewer / type / severity / disposition) narrows the list.
- [ ] Search matches RID, comment, and reply text.
- [ ] A duplicate row shows "↳ &lt;master&gt;"; a master shows "(N dup)".

## Detail pane and roles
- [ ] Selecting a finding shows the full comment, anchor, and reviewer.
- [ ] Owner mode: reply / disposition / resolution are editable; "→ answered" and "→ implemented" work.
- [ ] Owner mode: "→ verified" is **disabled** with a tooltip (the owner may never verify).
- [ ] Reviewer mode with "Acting as" set to the RID's reviewer: "→ verified" is enabled.
- [ ] Reviewer mode as a **different** reviewer: "→ verified" is disabled with a tooltip.
- [ ] "→ withdrawn" is offered only to the RID's own reviewer, and only from `open`.

## Dashboard
- [ ] Per-status counts and the total update as statuses change.
- [ ] "% closed" reflects verified + withdrawn over the total.

## Defensive
- [ ] Opening a non-RTD YAML shows an error and does not load.
- [ ] Saving is refused when the schema is invalid.

## Note
The written Step 4 DoD says the saved file should "pass `malus report` validation".
`report` arrives in Step 5; until then the saved file is validated by loading it
with the same Python model the CLI uses (`RTD.from_yaml`), which was done during
Step 4 verification.
