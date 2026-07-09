"""Smoke test: the package imports and exposes a version string."""

import malus


def test_version_is_nonempty_string() -> None:
    assert isinstance(malus.__version__, str)
    assert malus.__version__
