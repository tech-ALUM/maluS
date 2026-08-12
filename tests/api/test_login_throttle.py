"""Login throttling — anti-automation on credential checks (ADR 0005)."""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from malus.api import create_app
from malus.auth.throttle import LoginThrottle, ThrottlePolicy, TooManyAttempts
from malus.db import create_all, make_engine

ADMIN = ("admin", "admin-pw")
POLICY = ThrottlePolicy(max_attempts=3, ip_max_attempts=5, window_seconds=900)


@pytest.fixture
def app():
    engine = make_engine("sqlite://")
    create_all(engine)
    return create_app(
        engine,
        https_only=False,
        session_secret="test-secret",
        bootstrap_admin=ADMIN,
        login_policy=POLICY,
    )


@pytest.fixture
def client(app):
    return TestClient(app)


def _basic(username: str, password: str) -> dict:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _bad_login(client: TestClient, username: str = "admin", ip: str = "203.0.113.7"):
    return client.post(
        "/auth/login",
        json={"username": username, "password": "wrong"},
        headers={"X-Forwarded-For": ip},
    )


# --- the username dimension ------------------------------------------------ #


def test_repeated_failures_get_429_with_retry_after(client: TestClient):
    for _ in range(POLICY.max_attempts):
        assert _bad_login(client).status_code == 401
    blocked = _bad_login(client)
    assert blocked.status_code == 429
    assert 0 < int(blocked.headers["Retry-After"]) <= POLICY.window_seconds


def test_throttle_blocks_even_the_correct_password(client: TestClient):
    """The check runs before the password is verified, so a spent counter wins."""
    for _ in range(POLICY.max_attempts):
        _bad_login(client)
    good = client.post(
        "/auth/login",
        json={"username": ADMIN[0], "password": ADMIN[1]},
        headers={"X-Forwarded-For": "203.0.113.7"},
    )
    assert good.status_code == 429


def test_success_clears_the_username_counter(client: TestClient):
    for _ in range(POLICY.max_attempts - 1):  # one short of the limit
        assert _bad_login(client).status_code == 401
    ok = client.post(
        "/auth/login",
        json={"username": ADMIN[0], "password": ADMIN[1]},
        headers={"X-Forwarded-For": "203.0.113.7"},
    )
    assert ok.status_code == 200
    assert _bad_login(client).status_code == 401  # counter restarted, not throttled


def test_counters_are_per_username(client: TestClient):
    for _ in range(POLICY.max_attempts):
        _bad_login(client, username="admin")
    assert _bad_login(client, username="someone-else").status_code == 401


# --- the IP dimension ------------------------------------------------------ #


def test_password_spraying_trips_the_ip_counter(client: TestClient):
    """Each username stays under its own limit; the shared IP is what stops it."""
    for n in range(POLICY.ip_max_attempts):
        assert _bad_login(client, username=f"user{n}").status_code == 401
    assert _bad_login(client, username="yet-another").status_code == 429


def test_a_different_client_ip_is_not_punished(client: TestClient):
    for n in range(POLICY.ip_max_attempts):
        _bad_login(client, username=f"user{n}", ip="203.0.113.7")
    assert _bad_login(client, username="fresh", ip="198.51.100.4").status_code == 401


def test_only_the_last_forwarded_hop_is_trusted(client: TestClient):
    """A forged left-hand XFF entry must not let an attacker rotate identity."""
    for n in range(POLICY.ip_max_attempts):
        client.post(
            "/auth/login",
            json={"username": f"user{n}", "password": "wrong"},
            headers={"X-Forwarded-For": f"10.0.0.{n}, 203.0.113.7"},
        )
    spoofed = client.post(
        "/auth/login",
        json={"username": "late", "password": "wrong"},
        headers={"X-Forwarded-For": "10.9.9.9, 203.0.113.7"},
    )
    assert spoofed.status_code == 429


# --- the other credential surfaces ----------------------------------------- #


def test_http_basic_is_throttled_too(client: TestClient):
    """Basic auth is accepted on every protected route, so it is a guessing surface."""
    for _ in range(POLICY.max_attempts):
        r = client.get("/reviews", headers=_basic("admin", "wrong"))
        assert r.status_code == 401
    assert client.get("/reviews", headers=_basic("admin", "wrong")).status_code == 429


def test_the_gui_form_renders_its_own_429(client: TestClient):
    for _ in range(POLICY.max_attempts):
        client.post("/ui/login", data={"username": "admin", "password": "wrong"})
    blocked = client.post("/ui/login", data={"username": "admin", "password": "wrong"})
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"]
    assert "Too many failed attempts" in blocked.text  # HTML, not the JSON error model


# --- the window ------------------------------------------------------------ #


def test_failures_age_out_of_the_window(monkeypatch):
    """Unit-level: the sliding window forgets, without sleeping through it."""
    now = [1000.0]
    monkeypatch.setattr(LoginThrottle, "_now", staticmethod(lambda: now[0]))
    throttle = LoginThrottle(ThrottlePolicy(max_attempts=2, window_seconds=60))

    for _ in range(2):
        throttle.record("bob", "203.0.113.7", ok=False)
    with pytest.raises(TooManyAttempts):
        throttle.check("bob", "203.0.113.7")

    now[0] += 61
    throttle.check("bob", "203.0.113.7")  # window elapsed: no longer blocked


def test_the_username_key_is_case_and_space_insensitive():
    throttle = LoginThrottle(ThrottlePolicy(max_attempts=1))
    throttle.record("Bob", None, ok=False)
    with pytest.raises(TooManyAttempts):
        throttle.check("  bob  ", None)


def test_spent_buckets_do_not_leak():
    """Pruned keys are dropped, so the map cannot grow without bound."""
    now = [1000.0]
    throttle = LoginThrottle(ThrottlePolicy(max_attempts=5, window_seconds=60))
    throttle._now = lambda: now[0]  # type: ignore[method-assign]
    throttle.record("bob", "203.0.113.7", ok=False)
    assert throttle._failures
    now[0] += 61
    throttle.check("bob", "203.0.113.7")
    assert not throttle._failures
