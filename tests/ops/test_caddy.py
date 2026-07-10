"""Step 11 config tests: Caddy is in the compose stack, TLS on 80/443, app
reachable only on loopback, proxied over the network to app:8000."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text())


def test_compose_has_app_and_caddy_services():
    services = _compose()["services"]
    assert "app" in services and "caddy" in services


def test_caddy_publishes_80_and_443():
    caddy = _compose()["services"]["caddy"]
    assert "80:80" in caddy["ports"] and "443:443" in caddy["ports"]


def test_app_is_published_only_on_loopback():
    app = _compose()["services"]["app"]
    assert all(str(p).startswith("127.0.0.1:") for p in app.get("ports", []))


def test_caddy_has_cert_volume_and_proxies_to_app():
    caddy = _compose()["services"]["caddy"]
    # a named volume for ACME certs must persist
    assert any("caddy-data:/data" in str(v) for v in caddy["volumes"])
    caddyfile = (ROOT / "deploy" / "Caddyfile.docker").read_text()
    assert "reverse_proxy app:8000" in caddyfile
    assert "MALUS_DOMAIN" in caddyfile  # domain from the environment


def test_env_example_documents_the_domain():
    assert "MALUS_DOMAIN" in (ROOT / ".env.example").read_text()
