"""Login throttling — anti-automation on credential verification (ADR 0005).

Stdlib only: ADR 0002 keeps the core runtime dependency-clean, so this is a
sliding-window counter rather than a third-party rate limiter.

State lives on ``app.state.login_throttle`` (per app instance, not module
global) so tests are isolated from one another and each ``create_app`` starts
clean. That is correct for the deployed topology — ``docker-entrypoint.sh``
runs a single uvicorn process with no ``--workers`` — but it does **not**
survive a restart and is not shared across replicas; see ADR 0005
§Consequences before scaling out.

Two dimensions are counted independently and either one can block:

- **username** — stops password guessing against a known account (the admin
  bootstrapped from ``MALUS_ADMIN_USER``).
- **client IP** — stops password spraying, where one password is tried against
  many usernames and no single username ever trips its counter.

A successful authentication clears that username's failures, so a legitimate
user who mistypes and then succeeds is never left throttled.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

from fastapi import Request


class TooManyAttempts(Exception):
    """Raised when a credential check is refused before it is even attempted.

    Carries the seconds until the oldest counted failure leaves the window,
    which the 429 handler echoes as ``Retry-After``.
    """

    def __init__(self, retry_after: int) -> None:
        super().__init__("too many failed login attempts; try again later")
        self.retry_after = retry_after


def _env_int(name: str, default: int) -> int:
    """Read a positive int from the environment, falling back on anything unusable."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class ThrottlePolicy:
    """How many failures are tolerated per sliding window, per dimension."""

    max_attempts: int = 5
    ip_max_attempts: int = 20
    window_seconds: int = 900

    @classmethod
    def from_env(cls) -> "ThrottlePolicy":
        """Build from ``MALUS_LOGIN_*`` (documented in docs/ops/runbook.md)."""
        return cls(
            max_attempts=_env_int("MALUS_LOGIN_MAX_ATTEMPTS", cls.max_attempts),
            ip_max_attempts=_env_int("MALUS_LOGIN_IP_MAX_ATTEMPTS", cls.ip_max_attempts),
            window_seconds=_env_int("MALUS_LOGIN_WINDOW_SECONDS", cls.window_seconds),
        )


class LoginThrottle:
    """Thread-safe sliding-window failure counter keyed by username and by IP."""

    def __init__(self, policy: Optional[ThrottlePolicy] = None) -> None:
        self.policy = policy or ThrottlePolicy()
        self._lock = threading.Lock()
        self._failures: Dict[str, Deque[float]] = defaultdict(deque)

    # -- internals ---------------------------------------------------------- #

    @staticmethod
    def _now() -> float:
        return time.monotonic()  # immune to wall-clock jumps (NTP, DST)

    def _prune(self, key: str, now: float) -> Deque[float]:
        """Drop failures that have aged out, and forget keys that empty out."""
        bucket = self._failures[key]
        cutoff = now - self.policy.window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if not bucket:
            self._failures.pop(key, None)
        return bucket

    def _limit_for(self, key: str) -> int:
        return self.policy.ip_max_attempts if key.startswith("ip:") else self.policy.max_attempts

    @staticmethod
    def _keys(username: str, client_ip: Optional[str]) -> list[str]:
        keys = [f"user:{username.strip().lower()}"]
        if client_ip:
            keys.append(f"ip:{client_ip}")
        return keys

    # -- API ---------------------------------------------------------------- #

    def check(self, username: str, client_ip: Optional[str] = None) -> None:
        """Raise :class:`TooManyAttempts` if either counter is already spent.

        Called *before* verifying the password, so a throttled attacker never
        reaches argon2 — the throttle also sheds the CPU cost of the attack.
        """
        now = self._now()
        with self._lock:
            for key in self._keys(username, client_ip):
                bucket = self._prune(key, now)
                if len(bucket) >= self._limit_for(key):
                    elapsed = now - bucket[0]
                    retry_after = max(1, int(self.policy.window_seconds - elapsed))
                    raise TooManyAttempts(retry_after)

    def record(self, username: str, client_ip: Optional[str], *, ok: bool) -> None:
        """Record the outcome: a success clears the username, a failure counts.

        The IP counter is deliberately **not** cleared on success — otherwise one
        valid account would launder an ongoing spray from the same address.
        """
        now = self._now()
        user_key, *ip_keys = self._keys(username, client_ip)
        with self._lock:
            if ok:
                self._failures.pop(user_key, None)
                return
            for key in (user_key, *ip_keys):
                self._prune(key, now)
                self._failures[key].append(now)


def client_ip(request: Request) -> Optional[str]:
    """The real client address as seen by the edge proxy.

    maluS is published on loopback only and reached through the shared Caddy
    (docker-compose.yml, ``127.0.0.1:8000``), so ``request.client.host`` is
    Caddy's address on the compose network and is useless as an identity.
    Caddy *appends* the peer it accepted to ``X-Forwarded-For``, which makes
    the **last** element the address Caddy actually saw — the earlier ones are
    client-supplied and forgeable, so they are ignored.

    This trust holds only while nothing but the proxy can reach the app; if the
    port is ever published beyond loopback, this header becomes spoofable.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else None


def get_throttle(request: Request) -> Optional[LoginThrottle]:
    """The app's throttle, or ``None`` when one was never installed."""
    return getattr(request.app.state, "login_throttle", None)


def check(request: Request, username: str) -> None:
    """Guard a credential check. No-op when no throttle is installed."""
    throttle = get_throttle(request)
    if throttle is not None:
        throttle.check(username, client_ip(request))


def record(request: Request, username: str, *, ok: bool) -> None:
    """Record a credential-check outcome. No-op when no throttle is installed."""
    throttle = get_throttle(request)
    if throttle is not None:
        throttle.record(username, client_ip(request), ok=ok)
