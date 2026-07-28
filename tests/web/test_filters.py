"""Dashboard filter builder (v2.3): `?f=facet:op:value` conditions — OR
within a field (eq), AND across fields, ne excludes, comment contains —
plus the v2.2 rule: withdrawn hidden unless explicitly selected."""

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


def test_eq_or_within_field_and_across_fields(mkuser):
    owner, _f = _seed(mkuser)
    owner.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose", data={"disposition": "rejected", "reply": "no"})
    # 0001 answered/major, 0002 open/minor
    page = owner.get(f"/ui/reviews/{R}?f=status:eq:open&f=status:eq:answered").text
    assert "SIN-SRS-0001" in page and "SIN-SRS-0002" in page  # OR within status
    page = owner.get(f"/ui/reviews/{R}?f=status:eq:open&f=severity:eq:major").text
    assert "SIN-SRS-0001" not in page and "SIN-SRS-0002" not in page  # AND across


def test_ne_excludes(mkuser):
    owner, _f = _seed(mkuser)
    page = owner.get(f"/ui/reviews/{R}?f=severity:ne:minor").text
    assert "SIN-SRS-0001" in page and "SIN-SRS-0002" not in page


def test_comment_contains_case_insensitive(mkuser):
    owner, _f = _seed(mkuser)
    page = owner.get(f"/ui/reviews/{R}?f=comment:contains:TIMEOUT").text
    assert "SIN-SRS-0001" in page and "SIN-SRS-0002" not in page


def test_withdrawn_hidden_unless_selected(admin, mkuser):
    owner, _f = _seed(mkuser)
    owner.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose", data={"disposition": "rejected", "reply": "no"})
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    admin.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/retract")

    assert "SIN-SRS-0001" not in owner.get(f"/ui/reviews/{R}").text
    page = owner.get(f"/ui/reviews/{R}?f=status:eq:withdrawn").text
    assert "SIN-SRS-0001" in page and "SIN-SRS-0002" not in page


def test_builder_params_fold_into_canonical_url(mkuser):
    owner, _f = _seed(mkuser)
    r = owner.get(
        f"/ui/reviews/{R}?f=status:eq:open&facet=severity&op=ne&value=minor",
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].endswith("?f=status%3Aeq%3Aopen&f=severity%3Ane%3Aminor")


def test_tokens_render_with_remove_links(mkuser):
    owner, _f = _seed(mkuser)
    page = owner.get(f"/ui/reviews/{R}?f=status:eq:open&f=severity:ne:minor").text
    assert "<b>status</b> = open" in page and "<b>severity</b> ≠ minor" in page
    # removing one token keeps the other
    assert 'href="?f=severity%3Ane%3Aminor"' in page
    assert 'href="?f=status%3Aeq%3Aopen"' in page


def test_malformed_conditions_are_ignored(mkuser):
    owner, _f = _seed(mkuser)
    r = owner.get(f"/ui/reviews/{R}?f=banana&f=status:frobnicate:open&f=nofacet:eq:x")
    assert r.status_code == 200
    assert "SIN-SRS-0001" in r.text and "SIN-SRS-0002" in r.text  # no filtering applied


def test_actions_row_still_decluttered(mkuser):
    owner, _f = _seed(mkuser)
    page = owner.get(f"/ui/reviews/{R}").text
    assert "Implement accepted findings" not in page
    assert '<details class="menu">' in page
    owner.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose", data={"disposition": "accepted", "reply": "ok"})
    assert "Implement accepted findings" in owner.get(f"/ui/reviews/{R}").text
