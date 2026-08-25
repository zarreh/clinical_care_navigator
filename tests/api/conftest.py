from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.api._navigator_client import reset_navigator_overrides


@pytest.fixture(autouse=True)
def _clear_navigator_overrides() -> Iterator[None]:
    """Every API test starts and ends with a clean dependency-override table, so
    the stubbed graph one test installs never leaks into another."""
    reset_navigator_overrides()
    yield
    reset_navigator_overrides()
