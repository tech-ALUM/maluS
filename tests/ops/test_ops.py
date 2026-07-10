"""Deployment/operations smoke tests (v1 Step 8): healthcheck, structured
logging, and the presence/validity of the deploy artifacts (no Docker needed)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from malus.api import create_app
from malus.db import make_engine
from malus.logging import JsonFormatter

ROOT = Path(__file__).resolve().parents[2]


def test_health_endpoint_is_public_and_reports_version():
    client = TestClient(create_app(make_engine("sqlite://"), https_only=False))
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["version"]


def test_json_formatter_emits_valid_json_with_extras():
    record = logging.LogRecord("malus", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.request_id = "abc123"
    out = json.loads(JsonFormatter().format(record))
    assert out["level"] == "INFO"
    assert out["message"] == "hello world"
    assert out["request_id"] == "abc123"
    assert "ts" in out


def test_deployment_artifacts_exist():
    for rel in [
        "Dockerfile",
        "docker-compose.yml",
        ".env.example",
        "docker-entrypoint.sh",
        "deploy/Caddyfile",
        "scripts/backup.sh",
        "scripts/restore.sh",
        "docs/ops/runbook.md",
    ]:
        assert (ROOT / rel).is_file(), f"missing deploy artifact: {rel}"


def test_compose_is_valid_yaml_with_app_service():
    data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert "app" in data["services"]
    assert "malus-data" in data["volumes"]


def test_env_example_has_required_keys_and_no_committed_secret():
    text = (ROOT / ".env.example").read_text()
    for key in ("MALUS_DB_URL", "MALUS_SECRET_KEY", "MALUS_ADMIN_USER", "MALUS_ADMIN_PASSWORD"):
        assert key in text, f"missing key in .env.example: {key}"
    for line in text.splitlines():
        if line.startswith(("MALUS_SECRET_KEY=", "MALUS_ADMIN_PASSWORD=")):
            assert "CHANGE_ME" in line, f"committed a real-looking secret: {line}"
