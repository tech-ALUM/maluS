# maluS app icon — generation prompt

The icon used as favicon, apple-touch icon and PWA icon for the maluS web
application. It is **not** the ALUM company logo (that is `alum-logo.png` in
this folder): it is a product icon that must read as a sibling of the ALUM
mark without repeating it.

Paste the block below into an image model. Save the result in this folder as
`malus-icon.svg` (preferred) or `malus-icon.png`; the runtime sizes under
`src/malus/web/static/` are generated from it — see
`docs/plan/v3.2/01-brand.md` Task 3.

---

```
Design a flat vector app icon for "maluS", a tool for formal peer review of
technical documents. Square, 1024×1024, transparent background, plus a variant
on a #15181D ink background.

Brand system it must belong to (ALUM): coral #FF6F61, teal #0E7C86, ink
#15181D, paper #F7F8FA. The parent brand mark is an organic, liquid trefoil
with soft swollen curves and a negative-space letterform — the icon must feel
like it came from the same hand: fluid shapes, no hard geometry, generous
rounded terminals, flat fills only.

Concept: the proofreader's caret — the ∧ "insert here" mark editors write
between two lines of text. Build it as negative space cut out of one organic
coral shape, with a single teal accent element that reads as the correction
being inserted. It must say "a mark made in the margin", not "a document".

Hard constraints: flat vector, no gradients, no 3D, no bevel, no drop shadow,
no outline strokes. Maximum three colors. Must stay legible at 16×16 px:
one dominant shape, one accent, nothing thinner than 1/16 of the canvas.
Balanced optical margins, safe area for maskable icons.

Explicitly avoid these clichés: magnifying glass, page with a checkmark,
clipboard, red pen or pencil, speech bubble, eye, gear, "document with folded
corner", letter S in a rounded square.

Deliver: SVG source if possible, otherwise 1024×1024 PNG with transparency.
```

---

## Fallback concept

If the caret does not land, the alternative held in reserve is **the fold**:
the corner of a sheet curling over and becoming one lobe of the ALUM trefoil —
the document and the mark as the same gesture. Same constraints, same palette.

## Record

| Field | Value |
|---|---|
| Prompt author | this session, 2026-08-13 |
| Design decision | Alberto Boffi asked for an icon that is "non noiosa e scontata" — hence the explicit cliché ban |
| Generator used | _fill in when the asset is produced_ |
| Asset file | _fill in_ |
| Date produced | _fill in_ |

## Sources

- ALUM tokens and typography: `docs/brand/logo-prompt.md`, and the
  `alum-brand-identity` skill's `references/brand.md` cited by
  `docs/plan/v1.9/01-alum-refresh.md:64-69`.
- Icon surfaces to serve: `src/malus/web/templates/base.html:7-9`,
  `src/malus/web/static/manifest.json`.
