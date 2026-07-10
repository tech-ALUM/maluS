"""Authorized HTTP pipeline (FastAPI TestClient): the full review run over HTTP
with real roles, OpenAPI, and rtd.yaml export/import (v1 Step 4 on Step 3)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from malus.api import create_app
from malus.db import make_engine

R = "SIN-SRS-R1"


def test_openapi_is_served(client: TestClient):
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    body = spec.json()
    assert body["openapi"].startswith("3.")
    assert "/reviews/{review_id}/harvest" in body["paths"]
    assert "/auth/login" in body["paths"]
    assert client.get("/docs").status_code == 200


def test_full_pipeline_over_http(app, mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    f = mkuser("fmiccoli", "F. Miccoli")
    r = mkuser("rbianchi", "R. Bianchi")
    mod = mkuser("mod", "M. Mod")

    # owner creates the review and assigns members
    resp = owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    assert resp.status_code == 201 and resp.json()["owner"] == "A. Boffi"
    for name, role in [("F. Miccoli", "reviewer"), ("R. Bianchi", "reviewer"), ("M. Mod", "moderator")]:
        assert owner.post(f"/reviews/{R}/reviewers", json={"name": name, "role": role}).status_code == 200

    # owner freezes; reviewers submit their own copies
    assert owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]}).status_code == 200
    assert f.put(f"/reviews/{R}/copies/F. Miccoli", json={"content": docs["copy_f"]}).status_code == 200
    assert r.put(f"/reviews/{R}/copies/R. Bianchi", json={"content": docs["copy_r"]}).status_code == 200

    # moderator harvests + triages
    h = mod.post(f"/reviews/{R}/harvest")
    assert h.status_code == 200, h.text
    assert sorted(x["kind"] for x in h.json()["rids"]) == ["COMM", "COMM", "SUGG"]
    assert mod.post(f"/reviews/{R}/triage", json={"auto": True}).json()["applied"] >= 1

    # owner answers + implements 0001
    assert owner.patch(
        f"/reviews/{R}/rids/SIN-SRS-0001",
        json={"status": "answered", "disposition": "accepted", "reply": "ok"},
    ).status_code == 200
    assert owner.post(
        f"/reviews/{R}/changes",
        json={"content": docs["baseline"] + "\nbound\n", "rids": ["SIN-SRS-0001"]},
    ).status_code == 200
    assert owner.patch(f"/reviews/{R}/rids/SIN-SRS-0001", json={"status": "implemented"}).status_code == 200

    # closure authority: owner 403, another reviewer 403, the RID's own reviewer 200
    assert owner.post(f"/reviews/{R}/rids/SIN-SRS-0001/verify").status_code == 403
    assert r.post(f"/reviews/{R}/rids/SIN-SRS-0001/verify").status_code == 403
    assert f.post(f"/reviews/{R}/rids/SIN-SRS-0001/verify").status_code == 200

    # moderator closes out the rest on reviewers' behalf, owner finalizes
    for rid in owner.get(f"/reviews/{R}/rids").json():
        if rid["status"] == "verified":
            continue
        owner.patch(
            f"/reviews/{R}/rids/{rid['rid']}",
            json={"status": "answered", "disposition": "rejected", "reply": "n/a"},
        )
        assert mod.post(f"/reviews/{R}/rids/{rid['rid']}/verify").status_code == 200
    fin = owner.post(f"/reviews/{R}/finalize", json={})
    assert fin.status_code == 200 and fin.json()["finalized"] is True

    # export is valid rtd.yaml
    assert "SIN-SRS-R1" in owner.get(f"/reviews/{R}/export").text


def test_export_import_roundtrip_across_databases(app, mkuser, docs):
    owner = mkuser("owner", "A. Boffi")
    owner.post("/reviews", json={"review_id": R, "rid_prefix": "SIN-SRS"})
    owner.post(f"/reviews/{R}/freeze", json={"content": docs["baseline"]})
    yaml_text = owner.get(f"/reviews/{R}/export").text

    # a second server with its own DB + admin
    other_app = create_app(
        make_engine("sqlite://"), https_only=False, session_secret="s2", bootstrap_admin=("a", "pw")
    )
    other = TestClient(other_app)
    other.post("/auth/login", json={"username": "a", "password": "pw"})
    imported = other.request(
        "POST", "/reviews/import", content=yaml_text, headers={"Content-Type": "text/plain"}
    )
    assert imported.status_code == 201, imported.text
    assert imported.json()["review_id"] == R
