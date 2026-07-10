"""HTTP API tests (FastAPI TestClient): the full pipeline headless over HTTP,
OpenAPI, and the 404/403/409/422 error model (v1 Step 3)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from malus.api import create_app
from malus.db import make_engine


def build_client() -> TestClient:
    return TestClient(create_app(make_engine("sqlite://")))

BASELINE = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable.

## 3.3 Logging

All measurements are written to disk in CSV format.
"""

COPY_F = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable. {COMM|type=technical|sev=major: the timeout must have an upper bound to avoid an unbounded wait}

## 3.3 Logging

All measurements are written to disk in CSV format. {SUGG: "disk" -> "the configured store"}
"""

COPY_R = """# Sensor Interface Requirements

## 3.2.1 Timeouts

The acquisition timeout shall be configurable. {COMM|type=technical|sev=major: the timeout must have an upper bound to prevent an unbounded wait}

## 3.3 Logging

All measurements are written to disk in CSV format.
"""


def _create(client: TestClient) -> None:
    r = client.post(
        "/reviews",
        json={
            "review_id": "SIN-SRS-R1",
            "document_name": "baseline.md",
            "owner": "A. Boffi",
            "reviewers": ["F. Miccoli", "R. Bianchi"],
            "rid_prefix": "SIN-SRS",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["reviewers"] == ["F. Miccoli", "R. Bianchi"]


def test_openapi_is_served(client: TestClient):
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    body = spec.json()
    assert body["openapi"].startswith("3.")
    assert "/reviews/{review_id}/harvest" in body["paths"]
    assert client.get("/docs").status_code == 200


def test_full_pipeline_over_http(client: TestClient):
    _create(client)

    # freeze the baseline
    r = client.post("/reviews/SIN-SRS-R1/freeze", json={"content": BASELINE})
    assert r.status_code == 200 and r.json()["is_baseline"] is True

    # reviewer copies
    assert client.put("/reviews/SIN-SRS-R1/copies/F. Miccoli", json={"content": COPY_F}).status_code == 200
    assert client.put("/reviews/SIN-SRS-R1/copies/R. Bianchi", json={"content": COPY_R}).status_code == 200

    # harvest
    r = client.post("/reviews/SIN-SRS-R1/harvest")
    assert r.status_code == 200, r.text
    harvested = r.json()
    assert harvested["violations"] == []
    assert sorted(x["kind"] for x in harvested["rids"]) == ["COMM", "COMM", "SUGG"]

    # triage clusters the two near-identical COMMs
    r = client.post("/reviews/SIN-SRS-R1/triage", json={"auto": True})
    assert r.status_code == 200 and r.json()["applied"] >= 1

    # owner answers 0001 (accept), links a change, then implements
    r = client.patch(
        "/reviews/SIN-SRS-R1/rids/SIN-SRS-0001",
        json={"status": "answered", "disposition": "accepted", "reply": "Agreed."},
    )
    assert r.status_code == 200 and r.json()["status"] == "answered"

    r = client.post(
        "/reviews/SIN-SRS-R1/changes",
        json={"content": BASELINE + "\nbounded.\n", "rids": ["SIN-SRS-0001"], "note": "bound"},
    )
    assert r.status_code == 200 and r.json()["version"]["ordinal"] == 2

    r = client.patch("/reviews/SIN-SRS-R1/rids/SIN-SRS-0001", json={"status": "implemented"})
    assert r.status_code == 200 and r.json()["status"] == "implemented"

    # the owner may never verify (403); the RID's reviewer can
    assert (
        client.post("/reviews/SIN-SRS-R1/rids/SIN-SRS-0001/verify", json={"reviewer": "A. Boffi"}).status_code
        == 403
    )
    r = client.post("/reviews/SIN-SRS-R1/rids/SIN-SRS-0001/verify", json={"reviewer": "F. Miccoli"})
    assert r.status_code == 200 and r.json()["status"] == "verified"
    assert r.json()["verified_by"] == "F. Miccoli"

    # report + traceability
    rep = client.get("/reviews/SIN-SRS-R1/report").json()
    assert rep["errors"] == [] and "Review Minutes — SIN-SRS-R1" in rep["report"]
    trace = client.get("/reviews/SIN-SRS-R1/traceability").json()
    assert "SIN-SRS-0001" in trace["referenced"]

    # close out the rest, then finalize
    for rid in client.get("/reviews/SIN-SRS-R1/rids").json():
        if rid["status"] == "verified":
            continue
        client.patch(
            f"/reviews/SIN-SRS-R1/rids/{rid['rid']}",
            json={"status": "answered", "disposition": "rejected", "reply": "n/a"},
        )
        assert (
            client.post(
                f"/reviews/SIN-SRS-R1/rids/{rid['rid']}/verify", json={"reviewer": rid["reviewer"]}
            ).status_code
            == 200
        )
    r = client.post("/reviews/SIN-SRS-R1/finalize", json={})
    assert r.status_code == 200 and r.json()["finalized"] is True
    assert r.json()["status"] == "finalized"

    # export is valid rtd.yaml
    export = client.get("/reviews/SIN-SRS-R1/export")
    assert export.status_code == 200
    assert "SIN-SRS-R1" in export.text and "rids:" in export.text


def test_document_get_and_replace(client: TestClient):
    _create(client)
    assert client.post("/reviews/SIN-SRS-R1/document", json={"content": BASELINE}).status_code == 200
    got = client.get("/reviews/SIN-SRS-R1/document").json()
    assert got["content"] == BASELINE


def test_not_found_returns_404(client: TestClient):
    assert client.get("/reviews/NOPE").status_code == 404
    _create(client)
    assert client.get("/reviews/SIN-SRS-R1/rids/SIN-SRS-9999").status_code == 404
    assert (
        client.post("/reviews/SIN-SRS-R1/rids/SIN-SRS-9999/verify", json={"reviewer": "F. Miccoli"}).status_code
        == 404
    )


def test_duplicate_review_returns_409(client: TestClient):
    _create(client)
    r = client.post(
        "/reviews",
        json={"review_id": "SIN-SRS-R1", "owner": "A. Boffi", "document_name": "baseline.md"},
    )
    assert r.status_code == 409


def test_missing_required_field_returns_422(client: TestClient):
    r = client.post("/reviews", json={"review_id": "X"})  # no owner
    assert r.status_code == 422


def _seed_answered_accepted(client: TestClient) -> None:
    _create(client)
    client.post("/reviews/SIN-SRS-R1/freeze", json={"content": BASELINE})
    client.put("/reviews/SIN-SRS-R1/copies/F. Miccoli", json={"content": COPY_F})
    client.post("/reviews/SIN-SRS-R1/harvest")
    client.patch(
        "/reviews/SIN-SRS-R1/rids/SIN-SRS-0001",
        json={"status": "answered", "disposition": "accepted", "reply": "ok"},
    )


def test_implement_without_change_returns_409(client: TestClient):
    _seed_answered_accepted(client)
    # no RidChange linked yet -> traceability gate blocks the transition
    r = client.patch("/reviews/SIN-SRS-R1/rids/SIN-SRS-0001", json={"status": "implemented"})
    assert r.status_code == 409


def test_export_import_roundtrip_across_databases(client: TestClient):
    _seed_answered_accepted(client)
    yaml_text = client.get("/reviews/SIN-SRS-R1/export").text

    other = build_client()
    r = other.request("POST", "/reviews/import", content=yaml_text, headers={"Content-Type": "text/plain"})
    assert r.status_code == 201, r.text
    assert r.json()["review_id"] == "SIN-SRS-R1"
    # the imported review is queryable and carries the same RIDs
    rids = other.get("/reviews/SIN-SRS-R1/rids").json()
    assert any(x["rid"] == "SIN-SRS-0001" for x in rids)
