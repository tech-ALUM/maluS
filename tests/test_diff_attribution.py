"""v3.2 step 05 — every hunk names the finding behind it.

Step 04 made each document version the product of exactly one implementation
session, which is what makes provenance knowable at all: a version with one
cause can label the lines it wrote.
"""

from __future__ import annotations

from malus.diffing import Attribution, html_diff, line_provenance

BASELINE = """# Sensor Interface Requirements

The acquisition timeout shall be configurable.

All measurements are written to disk in CSV format.

Calibration coefficients live beside the measurement data.
"""

# A bounds the timeout
V1 = BASELINE.replace(
    "The acquisition timeout shall be configurable.",
    "The acquisition timeout shall be configurable, bounded to at most 30 s.",
)

# B sharpens what A wrote
V2 = V1.replace(
    "bounded to at most 30 s.",
    "bounded to at most 30 seconds, inclusive.",
)

# C deletes a baseline paragraph outright
V3 = V2.replace("Calibration coefficients live beside the measurement data.\n", "")

CHAIN = [
    (BASELINE, []),
    (V1, ["SIN-SRS-0001"]),
    (V2, ["SIN-SRS-0002"]),
    (V3, ["SIN-SRS-0003"]),
]


def test_a_line_carries_the_finding_that_last_wrote_it():
    prov = line_provenance(CHAIN)
    final = V3.splitlines()
    timeout = next(i for i, l in enumerate(final) if "bounded to at most" in l)

    # B rewrote A's line, so the line belongs to B — not to whoever touched it first
    assert prov.for_new_line(timeout) == ("SIN-SRS-0002",)


def test_untouched_baseline_lines_carry_nothing():
    prov = line_provenance(CHAIN)
    final = V3.splitlines()
    csv = next(i for i, l in enumerate(final) if "CSV" in l)

    assert prov.for_new_line(csv) == ()


def test_a_deletion_is_attributed_to_the_version_that_removed_it():
    prov = line_provenance(CHAIN)
    baseline = BASELINE.splitlines()
    calib = next(i for i, l in enumerate(baseline) if "Calibration" in l)

    # the deleted line has no successor to carry a label, so it is recorded
    # against the baseline index it occupied
    assert prov.for_old_line(calib) == ("SIN-SRS-0003",)


def test_one_session_may_carry_several_findings():
    """A change that resolves a cluster of duplicates labels its lines with all
    of them (v3.2 step 04 allows duplicates to be attached at close time)."""
    chain = [(BASELINE, []), (V1, ["SIN-SRS-0001", "SIN-SRS-0009"])]
    prov = line_provenance(chain)
    final = V1.splitlines()
    timeout = next(i for i, l in enumerate(final) if "bounded" in l)

    assert prov.for_new_line(timeout) == ("SIN-SRS-0001", "SIN-SRS-0009")


def test_an_empty_chain_is_not_an_error():
    assert line_provenance([]) == Attribution()
    assert line_provenance([(BASELINE, [])]).inserted == ((), (), (), (), (), (), ())


def test_the_rendered_diff_badges_insertions_and_deletions():
    prov = line_provenance(CHAIN)
    out = html_diff(BASELINE, V3, context=None, attribution=prov)

    assert 'class="diff-rid"' in out
    assert "SIN-SRS-0002" in out          # the surviving edit
    assert "SIN-SRS-0003" in out          # the deletion
    # the line nobody touched must not be labelled
    csv_row = next(r for r in out.split("<div ") if "CSV" in r)
    assert "diff-rid" not in csv_row


def test_a_badge_cannot_smuggle_markup():
    prov = Attribution(inserted=(('<img src=x onerror="alert(1)">',),), deleted={})
    out = html_diff("a\n", "b\n", attribution=prov)

    assert "<img" not in out
    assert "&lt;img" in out


def test_without_attribution_the_output_is_unchanged():
    """The per-finding Changes section and the v3.1 downloads read this
    function; attribution must be strictly opt-in."""
    plain = html_diff(BASELINE, V3)
    assert "diff-rid" not in plain
    assert plain == html_diff(BASELINE, V3, attribution=None)

    numbered = html_diff(BASELINE, V3, context=None, line_numbers=True)
    assert "diff-rid" not in numbered


def test_a_badge_links_to_its_comment_when_a_base_is_given():
    prov = line_provenance(CHAIN)
    page = html_diff(BASELINE, V3, context=None, attribution=prov,
                     rid_base="/ui/reviews/R/document?focus=")

    assert '<a class="diff-rid" href="/ui/reviews/R/document?focus=SIN-SRS-0002"' in page
    # the download passes no base, so its badges stay inert text
    artifact = html_diff(BASELINE, V3, context=None, attribution=prov)
    assert "<a class=" not in artifact
    assert '<span class="diff-rid"' in artifact


def test_a_linked_badge_cannot_break_out_of_its_href():
    prov = Attribution(inserted=(('" onmouseover="alert(1)',),), deleted={})
    out = html_diff("a\n", "b\n", attribution=prov, rid_base="/x?focus=")

    assert 'onmouseover="alert(1)"' not in out
    assert "&quot;" in out or "&#x27;" in out
