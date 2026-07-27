"""anchor.offset — baseline character offset persisted at harvest (v2 step 4a).

The offset is an additive, optional field of ``Anchor``: absent on pre-v2
RIDs (imports as ``None``), emitted in ``rtd.yaml`` only when set (old
exports stay byte-identical), and filled by ``build_rtd`` with the block's
baseline offset — the same value the viewer uses to place markers.
"""

import datetime as dt

from malus.harvest import build_rtd
from malus.models import RTD, Anchor, Meta

BASELINE = (
    "# Spec\n"
    "\n"
    "## 3.2.1 Timeouts\n"
    "\n"
    "The timeout shall be configurable.\n"
    "\n"
    "## 3.3 Logging\n"
    "\n"
    "Logs are written to disk.\n"
)

COMM = "{COMM|type=technical|sev=major: bound the timeout}"


def _meta() -> Meta:
    return Meta(
        review_id="SIN-SRS-R1",
        document="baseline.md",
        baseline_sha="abc1234",
        created=dt.date(2026, 7, 27),
        owner="A. Boffi",
        reviewers=["F. Miccoli"],
    )


def test_harvest_fills_anchor_offset() -> None:
    ins = BASELINE.index("configurable.") + len("configurable.")
    copy = BASELINE[:ins] + " " + COMM + BASELINE[ins:]
    res = build_rtd(BASELINE, _meta(), {"F. Miccoli": copy})
    rid = res.rtd.rids[0]
    # baseline coordinates: right after "configurable." (the extra inserted
    # space is copy whitespace, not part of the baseline)
    assert rid.anchor.offset == ins
    assert BASELINE[: rid.anchor.offset].endswith("configurable.")


def test_anchor_dict_roundtrip_is_additive() -> None:
    plain = Anchor(section="S", quote="q", line_hint=3)
    assert "offset" not in plain.to_dict()  # old exports stay identical
    assert Anchor.from_dict(plain.to_dict()).offset is None  # pre-v2 import

    with_off = Anchor(section="S", quote="q", line_hint=3, offset=42)
    d = with_off.to_dict()
    assert d["offset"] == 42
    assert Anchor.from_dict(d) == with_off


def test_rtd_yaml_roundtrip_preserves_offset() -> None:
    ins = BASELINE.index("disk") + len("disk")
    copy = BASELINE[:ins] + " " + COMM + BASELINE[ins:]
    rtd = build_rtd(BASELINE, _meta(), {"F. Miccoli": copy}).rtd
    again = RTD.from_yaml(rtd.to_yaml())
    assert again.rids[0].anchor.offset == rtd.rids[0].anchor.offset is not None
    # and a re-serialization is byte-identical (idempotent export)
    assert again.to_yaml() == rtd.to_yaml()
