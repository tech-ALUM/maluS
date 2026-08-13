# v3.2 Step 1 — Brand: the new ALUM mark, the maluS icon, the favicon set

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Goal:** the application wears the current ALUM identity. The sidebar mark
becomes the new logo Alberto supplied, and the app icon — today a dark tile
with a coral "S" — becomes a purpose-drawn maluS icon wired as favicon,
apple-touch icon and PWA icon.

Feedback point **1** of the v3.2 wave.

## Deliverables

- [ ] `docs/brand/` holds the sources; `src/malus/web/static/` holds only
      generated, committed runtime files
- [ ] The sidebar mark is the new ALUM mark, crisp at 20 px and 26 px
- [ ] The maluS app icon replaces `icon.svg` across favicon, apple-touch and
      manifest, in the sizes each surface actually needs
- [ ] A decision recorded on the coral token (see Task 1)
- [ ] `python -m pytest -q` green

## What is already known (measured this session — do not re-derive)

`docs/brand/alum-logo.png`, supplied by Alberto on 2026-08-13:

| Fact | Value |
|---|---|
| Size / mode | 1254 × 1254, RGBA, real alpha (min 0, max 255) |
| Ink rows | 220 → 962 |
| Mark band | rows 220–773 |
| Gap | rows 774–843 (70 px of nothing) |
| Wordmark band | rows 844–962 |
| Mark box (absolute) | x 329–930, y 220–774 → 601 × 554 |
| Wordmark box (absolute) | x 198–1052, y 844–963 |
| Dominant coral | **#FE5950** (80.5 % of opaque pixels) |
| Dominant teal | **#088092** (19.2 %) |
| Distinct opaque colours | 5712 — the new mark is **shaded**, not flat |

Tooling: **Pillow 12.3.0** is in `.venv` and is the only rasteriser available —
there is no ImageMagick, Inkscape or rsvg on this machine. Pillow is a
development tool here: it generates files that are then committed. It must not
become a runtime dependency and must not be added to `pyproject.toml`.

## Tasks

### Task 1: decide the coral token

The brand tokens locked since v1.9 are coral `#FF6F61`, teal `#0E7C86`, ink
`#15181D`, paper `#F7F8FA` (`docs/brand/logo-prompt.md`, ALUM brand identity
skill). The new logo does not use either accent token:

| | Locked token | New logo | Δ |
|---|---|---|---|
| Coral | `#FF6F61` | `#FE5950` | redder, more saturated |
| Teal | `#0E7C86` | `#088092` | bluer, brighter |

The old mark was flat two-colour; the new one is shaded (5712 distinct
opaque colours), so it carries depth the flat UI palette does not.

- [x] **Step 1:** both values measured (above).
- [x] **Step 2: decided by Alberto Boffi, 2026-08-13 — the UI adapts to the
      logo.** The accent tokens move: coral `#FF6F61` → **`#FE5950`**, teal
      `#0E7C86` → **`#088092`**. The logo is not repainted. The per-reviewer
      palette (`--rev-0..7`) is a separate system and is **not** touched.
The derived variants keep the exact role each token had: `-dark` keeps the same
relative darkening as before, `-soft` keeps the old tint's weight and
saturation and only moves the hue (that token is a near-white veil used for the
page gradient and button hover — recomputing it from the base would have made
it far heavier). Values to apply in `app.css:18-23`:

```css
  --coral: #fe5950;        /* was #ff6f61 */
  --coral-dark: #df463e;   /* was #e2564a */
  --coral-soft: #fff0ef;   /* was #fff1ef */
  --teal: #088092;         /* was #0e7c86 */
  --teal-dark: #056675;    /* was #0a636b */
  --teal-soft: #e6f1f3;    /* was #e6f2f3 */
```

Two literals escape the token system and must move with it: the coral shadows
`rgba(255, 111, 97, .35)` (`app.css:90`) and `rgba(255, 111, 97, .3)`
(`app.css:134`) become `rgba(254, 89, 80, …)`, and `manifest.json:9`
`theme_color` becomes `#FE5950`.

- [ ] **Step 3:** change the token definitions in `app.css` and walk every
      surface that derives from them — buttons, status pills, focus rings,
      role badges, banners, the progress ring — at 375 px and 1280 px, on the
      reviews list, a review dashboard, the document viewer in `in_review`
      and in `closeout`, Members and Users. Any hard-coded `#FF6F61` or
      `#0E7C86` left in templates or CSS is part of this sweep.
- [ ] **Step 4:** commit `feat(web): accent tokens follow the new ALUM logo`.

### Task 2: generate the ALUM mark

**Files:** create `src/malus/web/static/alum-mark.png`; move
`src/malus/web/static/alum-lockup-light.svg` and the superseded
`alum-mark.svg` to `docs/brand/legacy/`.

- [ ] **Step 1:** crop the mark band (x 329–930, y 220–774), pad it to a
      square canvas with equal optical margins, and export a 128 px PNG. It is
      displayed at 26 px (sidebar) and 20 px (mobile topbar), so 128 px covers
      every device pixel ratio in use.
- [ ] **Step 2:** point `base.html:19` and `base.html:52` at the new file,
      keeping `?v={{ asset_v }}` (the v2.0.1 rule: **never** add an asset link
      without it).
- [ ] **Step 3:** note in this file that a vector mark is being replaced by a
      raster, because Alberto supplied a PNG. If an SVG of the new logo ever
      arrives, swapping back is a one-file change.
- [ ] **Step 4:** commit `feat(web): the sidebar wears the new ALUM mark`.

### Task 3: the maluS app icon

**Files:** create `src/malus/web/static/icon-32.png`, `icon-180.png`,
`icon-192.png`, `icon-512.png`, `icon-maskable-512.png`; modify
`src/malus/web/templates/base.html`, `src/malus/web/static/manifest.json`;
delete `src/malus/web/static/icon.svg`.

Source: `docs/brand/malus-icon.*`, produced by Alberto from the prompt in
`docs/brand/malus-icon-prompt.md`. **If that source is not in the tree yet,
stop after Task 2 and say so** — do not invent an icon.

- [ ] **Step 1:** if the source is an SVG, keep it as the primary `rel="icon"`
      and generate the PNGs from it; if it is a PNG, generate all sizes from
      the largest available raster with `LANCZOS` resampling.
- [ ] **Step 2:** the maskable variant needs the icon inside the safe zone —
      scale the artwork to 80 % of the canvas on a solid `#15181D` field, so
      Android's circular crop never clips it.
- [ ] **Step 3:** rewrite the `<head>` block (`base.html:7-9`): `rel="icon"`
      with explicit `sizes`, `apple-touch-icon` → `icon-180.png`, manifest
      untouched in position. Update `manifest.json` icons to the real files
      and sizes, replacing the two `sizes: "any"` SVG entries.
- [ ] **Step 4:** `tests/web/test_assets.py` **already asserts** that
      `/static/icon.svg` is served and linked from `base.html`
      (`test_assets.py:8-17`) — deleting the file breaks it by design. Rewrite
      those two tests to walk **every** icon path referenced by `base.html`
      and `manifest.json` and assert 200 on each, so the suite guards the real
      failure mode: a renamed file silently 404ing behind a cached favicon.
      Leave the v2.0.1 cache tests (`test_assets.py:26-38`) alone.
- [ ] **Step 5:** commit `feat(web): maluS app icon, favicon and PWA set`.

### Task 4: prompt on record

**Files:** create `docs/brand/malus-icon-prompt.md`.

- [ ] **Step 1:** store the image-generation prompt used for the icon, next to
      `logo-prompt.md`, so the icon can be regenerated consistently. Record
      which tool produced the asset and on what date.
- [ ] **Step 2:** commit `docs(brand): the maluS icon prompt on record`.

## Definition of Done

- [ ] `.venv/bin/python -m pytest -q; echo EXIT=$?` → EXIT=0
- [ ] Every icon and mark URL in `base.html` and `manifest.json` returns 200
- [ ] Sidebar mark verified at 26 px and 20 px, and on the `≤900px` topbar
- [ ] No new entry in `pyproject.toml`; Pillow used only to produce committed
      files
- [ ] The coral-token decision of Task 1 is written down here
- [ ] Checkboxes ticked, deviations recorded under `## Deviations`

## Out of scope

- Restyling anything beyond the mark and the icon. If the coral token moves,
  that is a follow-up with its own visual regression pass, not part of this
  step.
- Producing a vector version of the ALUM logo by tracing the PNG.
