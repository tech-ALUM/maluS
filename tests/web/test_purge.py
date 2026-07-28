"""Admin-only permanent purge of a comment (v2.2). Normal delete keeps the
v1.8 semantics (pristine → hard-delete, acted-upon → withdrawn); purge
removes the RID definitively — the audit row is the only remaining trace."""

from __future__ import annotations

from sqlmodel import Session, select

from malus.db.models import RID, AuditLog

R = "SIN-SRS-R1"


def _seed(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    for name, role in [("F. Miccoli", "reviewer"), ("M. Mod", "moderator")]:
        owner.post(f"/reviews/{R}/reviewers", json={"name": name, "role": role})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/ui/reviews/{R}/edit-copy", data={"content": docs["copy_f"], "action": "save"})
    # acted upon: a plain delete would only withdraw it
    owner.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose", data={"disposition": "rejected", "reply": "no"})
    return owner, f, mod


def test_admin_purges_acted_upon_rid(app, admin, mkuser, docs):
    owner, _f, _mod = _seed(mkuser, docs)
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})

    r = admin.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/purge", follow_redirects=False)
    assert r.status_code == 303

    assert owner.get(f"/reviews/{R}/rids").json() == []  # gone from the API
    assert "SIN-SRS-0001" not in owner.get(f"/ui/reviews/{R}?status=withdrawn").text
    with Session(app.state.engine) as s:
        assert s.exec(select(RID)).all() == []  # row really deleted
        entry = s.exec(select(AuditLog).where(AuditLog.action == "purge_rid")).one()
        assert entry.actor.username == "admin"
        assert entry.detail_json["comment"]  # the final trace keeps the text
        assert entry.detail_json["reviewer"] == "F. Miccoli"


def test_purge_is_admin_only_and_404s_unknown(admin, mkuser, docs):
    owner, f, mod = _seed(mkuser, docs)
    for client in (owner, f, mod):
        assert client.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/purge").status_code == 403
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    assert admin.post(f"/ui/reviews/{R}/rids/SIN-SRS-9999/purge").status_code == 404
    # the finding survived every refused attempt
    assert len(owner.get(f"/reviews/{R}/rids").json()) == 1


def test_purging_a_master_clears_duplicate_backrefs(app, admin, mkuser, docs):
    _owner, _f, _mod = _seed(mkuser, docs)
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    with Session(app.state.engine) as s:  # forge a duplicate pointing at 0001
        master = s.exec(select(RID).where(RID.rid_str == "SIN-SRS-0001")).one()
        dup = RID(
            review_id=master.review_id, rid_str="SIN-SRS-0002", reviewer_id=master.reviewer_id,
            kind="COMM", comment="dup", master_id=master.id,
        )
        s.add(dup)
        s.commit()

    assert admin.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/purge", follow_redirects=False).status_code == 303
    with Session(app.state.engine) as s:
        survivor = s.exec(select(RID)).one()
        assert survivor.rid_str == "SIN-SRS-0002" and survivor.master_id is None
