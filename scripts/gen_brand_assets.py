"""Generate the committed runtime brand assets from the sources in docs/brand/.

Development tool: its output is committed and served statically. Pillow never
becomes a runtime dependency of maluS.

Usage:  .venv/bin/python <this file> <out-dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve()
BRAND = Path("docs/brand")
INK = (21, 24, 29, 255)  # #15181D


def trimmed(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    box = im.getchannel("A").getbbox()
    return im.crop(box) if box else im


def squared(im: Image.Image, margin: float = 0.0) -> Image.Image:
    """Centre `im` on a transparent square canvas with a relative margin."""
    w, h = im.size
    side = max(w, h)
    pad = int(side * margin)
    canvas = Image.new("RGBA", (side + 2 * pad, side + 2 * pad), (0, 0, 0, 0))
    canvas.paste(im, (pad + (side - w) // 2, pad + (side - h) // 2), im)
    return canvas


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # --- the ALUM mark: the lockup's upper band, without the wordmark -------
    # Measured 2026-08-13: mark band rows 220-773, wordmark rows 844-962.
    lockup = Image.open(BRAND / "alum-logo.png").convert("RGBA")
    mark = lockup.crop((0, 220, lockup.width, 774))
    box = mark.getchannel("A").getbbox()
    mark = squared(mark.crop(box), margin=0.06)
    mark.resize((128, 128), Image.LANCZOS).save(out / "alum-mark.png")
    written.append(out / "alum-mark.png")

    # --- the maluS app icon ------------------------------------------------
    icon = squared(trimmed(BRAND / "malus-icon.png"), margin=0.02)
    for size in (32, 180, 192, 512):
        icon.resize((size, size), Image.LANCZOS).save(out / f"icon-{size}.png")
        written.append(out / f"icon-{size}.png")

    # Maskable: Android crops to a circle, so the artwork must sit inside the
    # safe zone (80% of the canvas) on an opaque field.
    canvas = Image.new("RGBA", (512, 512), INK)
    art = icon.resize((410, 410), Image.LANCZOS)
    canvas.paste(art, (51, 51), art)
    canvas.save(out / "icon-maskable-512.png")
    written.append(out / "icon-maskable-512.png")

    for f in written:
        print(f"{f.name:24} {Image.open(f).size}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
