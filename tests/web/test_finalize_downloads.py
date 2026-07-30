"""v3 step 04: finalize flow + finalized downloads (final MD, report, PDF)."""

from __future__ import annotations

R = "SIN-SRS-R1"
FINAL_MD = "# Sensor Interface Requirements\n\nThe acquisition timeout shall be bounded.\n"


def _to_closeout(mkuser, docs):
    """Owner+reviewer, one accepted RID implemented and verified in closeout."""
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "M. Mod", "role": "moderator"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    mod.post(f"/reviews/{R}/harvest")
    for resp in (
        owner.post(
            f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
            data={"disposition": "accepted", "reply": "ok"},
            follow_redirects=False,
        ),
        f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept", follow_redirects=False),
        owner.post(f"/ui/reviews/{R}/start-closeout", follow_redirects=False),
        owner.post(
            f"/ui/reviews/{R}/closeout",
            data={"content": FINAL_MD, "rids": ["SIN-SRS-0001"]},
            follow_redirects=False,
        ),
        owner.post(
            f"/ui/reviews/{R}/rids/SIN-SRS-0001/implement",
            data={"resolution": "bounded"},
            follow_redirects=False,
        ),
        f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/verify", follow_redirects=False),
    ):
        assert resp.status_code == 303, resp.text[:300]
    return owner, f


def test_finalize_blocked_until_gate_holds(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    mod = mkuser("mod", "M. Mod")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{R}/reviewers", json={"name": "M. Mod", "role": "moderator"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    f.post(f"/reviews/{R}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    mod.post(f"/reviews/{R}/harvest")
    owner.post(
        f"/ui/reviews/{R}/rids/SIN-SRS-0001/dispose",
        data={"disposition": "accepted", "reply": "ok"},
    )
    f.post(f"/ui/reviews/{R}/rids/SIN-SRS-0001/accept")
    owner.post(f"/ui/reviews/{R}/start-closeout")
    # accepted RID not yet verified → 409, dashboard shows no Terminate button
    assert "Terminate review" not in owner.get(f"/ui/reviews/{R}").text
    assert owner.post(f"/ui/reviews/{R}/finalize").status_code == 409


def test_finalize_flow_and_downloads(mkuser, docs):
    owner, f = _to_closeout(mkuser, docs)

    page = owner.get(f"/ui/reviews/{R}").text
    assert "Terminate review" in page  # gate satisfied → button appears

    r = owner.post(f"/ui/reviews/{R}/finalize", follow_redirects=False)
    assert r.status_code == 303
    page = owner.get(f"/ui/reviews/{R}").text
    assert "finalized" in page and "final.md" in page and "report.md" in page

    # downloads — for any member, owner and reviewer alike
    for client in (owner, f):
        r = client.get(f"/ui/reviews/{R}/download/final.md")
        assert r.status_code == 200 and r.text == FINAL_MD
        assert "attachment" in r.headers["content-disposition"]
        r = client.get(f"/ui/reviews/{R}/download/report.md")
        assert r.status_code == 200 and "Review Minutes" in r.text

    # PDF: archived when the extra is installed, explanatory 404 otherwise
    from malus import pdfgen

    r = owner.get(f"/ui/reviews/{R}/download/review.pdf")
    if pdfgen.PDF_AVAILABLE:
        assert r.status_code == 200 and r.content.startswith(b"%PDF")
        assert r.headers["content-type"] == "application/pdf"
    else:
        assert r.status_code == 404 and "malus[pdf]" in r.text


def test_finalize_owner_only_and_downloads_members_only(mkuser, docs):
    owner, _f = _to_closeout(mkuser, docs)
    outsider = mkuser("nobody", "No Body")
    assert outsider.post(f"/ui/reviews/{R}/finalize").status_code == 403
    owner.post(f"/ui/reviews/{R}/finalize")
    assert outsider.get(f"/ui/reviews/{R}/download/final.md").status_code == 403


def test_downloads_require_finalized_phase(mkuser, docs):
    owner, _f = _to_closeout(mkuser, docs)
    assert owner.get(f"/ui/reviews/{R}/download/final.md").status_code == 409
    # ...but the print fallback works already during closeout
    r = owner.get(f"/ui/reviews/{R}/print")
    assert r.status_code == 200 and "print-sheet" in r.text and "window.print()" in r.text


def test_dashboard_button_reads_terminate_review(mkuser, docs):
    """v3.1 step 02: user-facing wording only — phase, service and route keep
    the `finalize` vocabulary."""
    owner, _f = _to_closeout(mkuser, docs)
    page = owner.get(f"/ui/reviews/{R}").text
    assert "Terminate review" in page
    assert "Finalize review" not in page
    assert "Terminate the review?" in page                 # new confirm text
    assert f'action="/ui/reviews/{R}/finalize"' in page    # route unchanged


def test_reopen_terminated_is_human_admin_only(mkuser, docs):
    owner, f = _to_closeout(mkuser, docs)
    ai_admin = mkuser("aiadmin", "AI Admin", is_ai=True, is_admin=True)
    assert owner.post(f"/ui/reviews/{R}/finalize", follow_redirects=False).status_code == 303

    for client in (owner, f, ai_admin):  # owner: never; AI admin: is_ai is absolute
        assert client.post(
            f"/ui/reviews/{R}/reopen-terminated", follow_redirects=False
        ).status_code == 403
    assert owner.get(f"/reviews/{R}").json()["status"] == "finalized"  # untouched


def test_reopen_terminated_admin_flips_back_to_closeout_and_audits(app, mkuser, docs, admin):
    owner, _f = _to_closeout(mkuser, docs)
    owner.post(f"/ui/reviews/{R}/finalize")
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})

    r = admin.post(f"/ui/reviews/{R}/reopen-terminated", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith(f"/ui/reviews/{R}")
    assert owner.get(f"/reviews/{R}").json()["status"] == "closeout"

    from sqlmodel import Session, select

    from malus.db.models import AuditLog

    with Session(app.state.engine) as s:
        entry = s.exec(select(AuditLog).where(AuditLog.action == "reopen_finalized")).one()
        assert entry.target == f"review:{R}" and entry.actor.username == "admin"


def test_reopen_terminated_wrong_phase_is_409(mkuser, docs, admin):
    _owner, _f = _to_closeout(mkuser, docs)  # closeout, never terminated
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    assert admin.post(
        f"/ui/reviews/{R}/reopen-terminated", follow_redirects=False
    ).status_code == 409


def test_re_terminate_after_reopen_supersedes_final_and_pdf(app, mkuser, docs, admin):
    """The v3.1 design claim, end to end: history keeps both finals, the
    downloads serve the newest (VersionRepo.latest / ArtifactRepo.get)."""
    owner, _f = _to_closeout(mkuser, docs)
    owner.post(f"/ui/reviews/{R}/finalize")
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})
    admin.post(f"/ui/reviews/{R}/reopen-terminated")

    second = FINAL_MD + "\nAdded after the reopen.\n"
    assert owner.post(
        f"/ui/reviews/{R}/closeout",
        data={"content": second, "rids": ["SIN-SRS-0001"]},
        follow_redirects=False,
    ).status_code == 303
    assert owner.post(f"/ui/reviews/{R}/finalize", follow_redirects=False).status_code == 303
    assert owner.get(f"/ui/reviews/{R}/download/final.md").text == second

    from sqlmodel import Session, select

    from malus.db.models import DocumentVersion, ReviewArtifact

    from malus import pdfgen

    with Session(app.state.engine) as s:
        finals = s.exec(
            select(DocumentVersion).where(DocumentVersion.is_final == True)  # noqa: E712
        ).all()
        assert len(finals) == 2  # the superseded final stays in history
        if pdfgen.PDF_AVAILABLE:
            pdfs = s.exec(select(ReviewArtifact).where(ReviewArtifact.kind == "pdf")).all()
            assert len(pdfs) == 2


def test_reopen_entry_shows_only_for_a_human_admin_on_a_terminated_review(mkuser, docs, admin):
    owner, _f = _to_closeout(mkuser, docs)
    admin.post("/ui/account/password", data={"current": "admin-pw", "new_password": "admin-pw"})

    assert "/reopen-terminated" not in admin.get(f"/ui/reviews/{R}").text  # closeout: not yet

    owner.post(f"/ui/reviews/{R}/finalize")
    page = admin.get(f"/ui/reviews/{R}").text
    assert "/reopen-terminated" in page and "Reopen terminated review" in page
    assert "Reopen this terminated review?" in page   # first confirm
    assert "Really reopen" in page                    # second confirm

    assert "/reopen-terminated" not in owner.get(f"/ui/reviews/{R}").text  # owner: never
    ai_admin = mkuser("aiadmin", "AI Admin", is_ai=True, is_admin=True)
    assert "/reopen-terminated" not in ai_admin.get(f"/ui/reviews/{R}").text  # is_ai bar
