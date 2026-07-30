"""v3.1 step 04: /ui/reviews carries the download menu on finalized rows, and
the archived-PDF flag that feeds it comes from ONE batched query — not one per
row (`reviews_page` renders every review in the instance)."""

from __future__ import annotations

from sqlalchemy import event


def _finalize_review(owner, reviewer, review_id: str, docs) -> None:
    """Freeze → comment → harvest → accept → closeout → implement → verify →
    finalize, leaving `review_id` in phase `finalized`."""
    rid = f"{review_id}-0001"
    owner.post("/reviews", json={"review_id": review_id, "rid_prefix": review_id})
    owner.post(f"/reviews/{review_id}/reviewers", json={"name": "F. Miccoli", "role": "reviewer"})
    owner.post(f"/reviews/{review_id}/freeze", json={"content": docs["baseline"]})
    reviewer.post(f"/reviews/{review_id}/copies/F. Miccoli/submit", json={"content": docs["copy_f"]})
    owner.post(f"/reviews/{review_id}/harvest")
    owner.post(
        f"/ui/reviews/{review_id}/rids/{rid}/dispose",
        data={"disposition": "accepted", "reply": "ok"},
    )
    reviewer.post(f"/ui/reviews/{review_id}/rids/{rid}/accept")
    owner.post(f"/ui/reviews/{review_id}/start-closeout")
    owner.post(
        f"/ui/reviews/{review_id}/closeout",
        data={"content": docs["baseline"].replace("configurable", "bounded"), "rids": [rid]},
    )
    owner.post(f"/ui/reviews/{review_id}/rids/{rid}/implement", data={"resolution": "bounded"})
    reviewer.post(f"/ui/reviews/{review_id}/rids/{rid}/verify")
    r = owner.post(f"/ui/reviews/{review_id}/finalize", follow_redirects=False)
    assert r.status_code == 303, r.text[:300]


def test_menu_appears_only_on_finalized_rows(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    _finalize_review(owner, f, "REV-A", docs)
    owner.post("/reviews", json={"review_id": "REV-B", "rid_prefix": "REV-B"})
    owner.post("/reviews/REV-B/freeze", json={"content": docs["baseline"]})

    page = owner.get("/ui/reviews").text
    for name in ("baseline.md", "final.md", "diff.html", "report.md"):
        assert f"/ui/reviews/REV-A/download/{name}" in page
    assert "/ui/reviews/REV-B/download/" not in page  # still in review → no menu


def test_non_member_row_carries_no_download_menu(mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    _finalize_review(owner, f, "REV-A", docs)
    outsider = mkuser("out", "Out Sider")

    page = outsider.get("/ui/reviews").text
    assert "REV-A" in page                            # the row is listed…
    assert "/ui/reviews/REV-A/download/" not in page  # …without members-only links


def test_pdf_lookup_is_batched_not_one_query_per_row(app, mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    for review_id in ("REV-A", "REV-B", "REV-C"):
        _finalize_review(owner, f, review_id, docs)

    seen: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):
        seen.append(statement)

    engine = app.state.engine  # create_app stores it (api/deps.get_session reads it)
    event.listen(engine, "before_cursor_execute", _record)
    try:
        page = owner.get("/ui/reviews")
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert page.status_code == 200
    hits = [s for s in seen if "review_artifacts" in s.lower()]
    assert len(hits) == 1, f"expected 1 batched artifact query for 3 rows, got {len(hits)}"
