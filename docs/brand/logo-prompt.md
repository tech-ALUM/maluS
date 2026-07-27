# maluS — logo generation prompt

Ready to paste into ChatGPT (or any image generator). Source: maluS v2 design,
`docs/plan/v2/00-design.md` §10, approved by Alberto Boffi on 2026-07-27.
Colors and type follow the ALUM brand identity (coral `#FF6F61`, teal
`#0E7C86`, ink `#15181D`, Space Grotesk).

---

Design a modern, organic logo for "maluS", a document-review web app by
the brand ALUM. Concept: a document page merging with a review checkmark
or a soft magnifying lens, drawn as one continuous rounded shape. Style:
flat vector, minimal, friendly-professional, generous rounded corners,
no gradients, no 3D, no skeuomorphism. Colors, exactly these: coral
#FF6F61 as the primary accent, deep teal #0E7C86 as the secondary, ink
#15181D for dark strokes/text, on white. Typography for the wordmark:
geometric grotesque similar to Space Grotesk, lowercase "malu" with a
capital final "S" ("maluS"), the "S" in coral. Deliver: (1) icon-only
mark, (2) horizontal lockup icon + wordmark; each on white and on ink
#15181D backgrounds. Composition must stay legible at 24 px, suitable
for conversion to a clean SVG favicon.

---

Tips for iteration:

- If results are too busy, append: "single-weight strokes, at most two
  shapes, no texture, no shadows".
- For the favicon variant, append: "crop the icon-only mark on a square
  canvas with 10% padding".
- Ask for SVG output or vectorize the chosen PNG before replacing
  `src/malus/web/static/icon.svg` / `alum-mark.svg` (keep the ALUM mark —
  the maluS logo is the product mark, not a replacement for the company
  mark).
