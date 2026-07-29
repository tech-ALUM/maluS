"""v1.8: a reviewer retracts their own comment — pristine → hard-deleted (gone
from the table), owner-disposed → kept as `withdrawn`. Plus the submissions
panel sits at the top."""

from __future__ import annotations

R = "SIN-SRS-R1"

COPY_R = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable. {COMM|type=editorial|sev=minor: reword please}

## 3.3 Logging

All measurements are written to disk in CSV format.
"""


def _seed(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    r = mkuser("rbianchi", "R. Bianchi")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "R. Bianchi", "role": "reviewer"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    return owner, f, r


def _rids(client):
    return {x["rid"]: x for x in client.get(f"/reviews/{R}/rids").json()}


# --- (a) editor: removing a comment + submitting makes it disappear --------- #


def test_editor_removing_pristine_comment_hard_deletes_it(mkuser, docs):
    owner, f, _r = _seed(mkuser, docs)
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    assert "SIN-SRS-0001" in _rids(owner)  # harvested
    # resubmit the copy with the comment removed (back to the bare baseline)
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["baseline"], "action": "submit"})
    assert "SIN-SRS-0001" not in _rids(owner)  # gone, not lingering as withdrawn


def test_disposed_comment_withdraws_only_via_reopen(mkuser, docs):
    """v3: a disposed comment cannot vanish by editing the copy (the save is
    refused); the legal path is reopen -> retract, which keeps its history."""
    owner, f, _r = _seed(mkuser, docs)
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    owner.patch(f"/reviews/{R}/rids/SIN-SRS-0001", json={"status": "answered", "disposition": "rejected", "reply": "no"})

    # editing the block away is refused outright
    resp = f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["baseline"], "action": "submit"})
    assert resp.status_code == 422
    assert _rids(owner)["SIN-SRS-0001"]["status"] == "answered"

    # legal v3 path: reopen (reason) then retract -> kept as withdrawn
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/reopen", data={"reason": "retracting it"})
    resp = f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/retract", follow_redirects=False)
    assert resp.status_code == 303
    rids = _rids(owner)
    assert "SIN-SRS-0001" in rids and rids["SIN-SRS-0001"]["status"] == "withdrawn"  # history kept


# --- (b) table: a reviewer deletes their own open comment ------------------- #


def test_reviewer_retracts_own_open_comment_from_table(mkuser, docs):
    owner, f, _r = _seed(mkuser, docs)
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    resp = f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/retract", follow_redirects=False)
    assert resp.status_code == 303
    assert "SIN-SRS-0001" not in _rids(owner)  # gone from the table
    copy = f.get(f"/reviews/{R}/copies/F. Miccoli").json()["content"]
    assert "bound the timeout" not in copy  # and gone from the reviewer's copy


def test_cannot_retract_another_reviewers_comment(mkuser, docs):
    _owner, f, r = _seed(mkuser, docs)
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    assert r.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/retract").status_code == 403


def test_cannot_retract_a_disposed_comment(mkuser, docs):
    owner, f, _r = _seed(mkuser, docs)
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "ok", "resolution": ""},
    )
    assert f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/retract").status_code == 409
    assert "SIN-SRS-0001" in _rids(f)  # survived


def test_table_shows_retract_only_on_own_open_comment(mkuser, docs):
    owner, f, _r = _seed(mkuser, docs)
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    # the author sees a retract control; the owner does not
    assert "/retract" in f.get(f"/ui/reviews/{R}").text
    assert "/retract" not in owner.get(f"/ui/reviews/{R}").text


# --- (c) submissions panel is at the top ------------------------------------ #


# --- (d) v3: retract is in_review-only ------------------------------------- #


def test_retract_form_hidden_and_gated_in_closeout(admin, mkuser, docs):
    """v3 decision (step-close correction): retract_comment is gated to
    in_review only — the RTD-table withdraw control (own-open reviewer OR
    admin) must disappear once the review moves into closeout, and the route
    itself refuses (409) rather than silently no-op'ing. The admin any-phase
    path is reopen_review -> withdraw -> start_closeout; purge stays any-phase."""
    owner, f, _r = _seed(mkuser, docs)
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "submit"})
    owner.patch(
        f"/reviews/{R}/rids/SIN-SRS-0001",
        json={"status": "answered", "disposition": "accepted", "reply": "ok"},
    )
    assert f.post(f"/reviews/{R}/rids/SIN-SRS-0001/accept").status_code == 200
    assert owner.post(f"/reviews/{R}/start-closeout").status_code == 200

    # gone from the dashboard for both the owning reviewer and an admin
    assert "/retract" not in f.get(f"/ui/reviews/{R}").text
    assert "/retract" not in admin.get(f"/ui/reviews/{R}").text

    # and the route itself now refuses (phase conflict), not a silent no-op
    resp = admin.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/retract")
    assert resp.status_code == 409


def test_submissions_panel_is_above_the_table(mkuser, docs):
    owner, _f, _r = _seed(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}").text
    assert "subm-line" in page and 'class="rtd"' in page  # slim row since v2.2
    assert page.index("subm-line") < page.index('class="rtd"')  # submissions first
