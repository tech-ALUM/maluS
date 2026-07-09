"""Generate the JS constant block embedded in ``gui/rtd.html``.

The status-transition table and enumerations are defined once in
:mod:`malus.constants`. This module renders them as a JS ``const MALUS = {...}``
block so the GUI enforces the exact same rules; a test asserts the block in
``gui/rtd.html`` stays in sync. Regenerate with::

    python -m malus.gui_constants gui/rtd.html
"""

from __future__ import annotations

import json
import re
from enum import Enum
from pathlib import Path

from .constants import (
    TERMINAL_STATUSES,
    TRANSITIONS,
    CommentType,
    Disposition,
    Kind,
    Role,
    Severity,
    Status,
)

BEGIN = "// BEGIN GENERATED CONSTANTS (from malus.constants — regenerate, do not hand-edit)"
END = "// END GENERATED CONSTANTS"


def _values(enum: type[Enum]) -> list[str]:
    return [member.value for member in enum]


def render_block() -> str:
    """Return the ``BEGIN … const MALUS = {…}; … END`` JS block."""
    data = {
        "STATUSES": _values(Status),
        "KINDS": _values(Kind),
        "TYPES": _values(CommentType),
        "SEVERITIES": _values(Severity),
        "DISPOSITIONS": _values(Disposition),
        "ROLES": _values(Role),
        "TRANSITIONS": {
            status.value: sorted(target.value for target in targets)
            for status, targets in TRANSITIONS.items()
        },
        "TERMINAL": sorted(status.value for status in TERMINAL_STATUSES),
    }
    return f"{BEGIN}\nconst MALUS = {json.dumps(data, indent=2)};\n{END}"


def patch_file(path: Path | str) -> None:
    """Replace the generated block between the markers in ``path`` in place."""
    path = Path(path)
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END), re.DOTALL)
    text = path.read_text(encoding="utf-8")
    if not pattern.search(text):
        raise ValueError(f"generated-constants markers not found in {path}")
    path.write_text(pattern.sub(lambda _m: render_block(), text), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    import sys

    patch_file(sys.argv[1])
