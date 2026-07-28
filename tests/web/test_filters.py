"""Dashboard chip filters (v2.2): multi-select via repeated query params,
withdrawn hidden by default, decluttered actions row."""

from __future__ import annotations

R = "SIN-SRS-R1"

BASELINE = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable.

## 3.3 Logging

All measurements are written to disk in CSV format.
"""

COPY_TWO = BASELINE.replace(
    "configurable.",
    "configurable. {COMM|type=technical|sev=major: bound the timeout}",
).replace(
    "CSV format.",
    "CSV format. {COMM|type=editorial|sev=minor: specify the path}",
)


def _seed(mkuser):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": BASELINE})
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": COPY_TWO, "action": "save"})
    return owner, f


def _withdraw(owner, admin, rid):
    """Acted-upon + admin retract → withdrawn (v1.8 semantics)."""
    owner.post(f"/ui/reviews/{R}/rids/{rid}/dispose", data={"disposition": "rejected", "reply": "no"})
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    admin.post(f"/ui/reviews/{R}/rids/{rid}/retract")


def test_withdrawn_hidden_by_default_and_toggleable(admin, mkuser):
    owner, _f = _seed(mkuser)
    _withdraw(owner, admin, "SIN-SRS-0001")

    page = owner.get(f"/ui/reviews/{R}").text
    assert "SIN-SRS-0002" in page
    assert "SIN-SRS-0001" not in page  # withdrawn hidden by default

    page = owner.get(f"/ui/reviews/{R}?status=withdrawn").text
    assert "SIN-SRS-0001" in page and "SIN-SRS-0002" not in page


def test_multi_select_filters(admin, mkuser):
    owner, _f = _seed(mkuser)
    owner.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose", data={"disposition": "rejected", "reply": "no"})
    # 0001 answered, 0002 open
    page = owner.get(f"/ui/reviews/{R}?status=open&status=answered").text
    assert "SIN-SRS-0001" in page and "SIN-SRS-0002" in page
    page = owner.get(f"/ui/reviews/{R}?status=answered").text
    assert "SIN-SRS-0001" in page and "SIN-SRS-0002" not in page
    # facets AND together
    page = owner.get(f"/ui/reviews/{R}?status=open&severity=major").text
    assert "SIN-SRS-0001" not in page and "SIN-SRS-0002" not in page  # 0002 is minor


def test_chip_hrefs_toggle(mkuser):
    owner, _f = _seed(mkuser)
    page = owner.get(f"/ui/reviews/{R}?status=open").text
    assert 'href="?status=open&amp;status=answered"' in page or 'href="?status=open&status=answered"' in page
    # the active chip's href removes its own value
    assert 'class="chip-filter active" href="?"' in page


def test_actions_row_decluttered(mkuser):
    owner, f = _seed(mkuser)
    page = owner.get(f"/ui/reviews/{R}").text
    # no accepted findings yet → no Implement button; menu holds the rest
    assert "Implement accepted findings" not in page
    assert f'class="btn" href="/ui/reviews/{R}/members"' not in page  # duplicate gone
    assert "Copy review link" in page and "Delete review" in page  # in the ⋯ menu
    assert '<details class="menu">' in page

    owner.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose", data={"disposition": "accepted", "reply": "ok"})
    page = owner.get(f"/ui/reviews/{R}").text
    assert "Implement accepted findings" in page  # appears with work to do
