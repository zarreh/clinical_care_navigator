"""Exit criterion (c): the per-client rate limit is demonstrably enforced
(docs/PLAN.md §7 Phase 6, §5.6). Uses the walking-skeleton stream endpoint —
also rate-limited — so the limit is proven without spinning the real graph."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from navigator.api.main import app
from navigator.api.rate_limit import limiter
from navigator.settings import get_settings
from tests.api._navigator_client import build_navigator_test_context


def test_rate_limit_rejects_after_the_configured_ceiling() -> None:
    limiter.reset()
    ceiling = get_settings().rate_limit_per_minute
    client = TestClient(app)

    statuses = [
        client.post("/conversations/stream", json={"question": "hi"}).status_code
        for _ in range(ceiling + 1)
    ]

    assert statuses.count(200) == ceiling
    assert statuses[-1] == 429
    limiter.reset()


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/reviews", None),
        ("GET", "/conversations/nope", None),
        ("GET", "/conversations/nope/events", None),
        ("POST", "/reviews/nope/decision", {"action": "approve"}),
    ],
)
def test_every_real_route_is_rate_limited(
    tmp_path: Path, method: str, path: str, body: dict[str, str] | None
) -> None:
    # The skeleton-only test above left these undecorated and nobody noticed.
    limiter.reset()
    ctx = build_navigator_test_context(tmp_path, scope_violation=False)
    ceiling = get_settings().rate_limit_per_minute

    statuses = [ctx.client.request(method, path, json=body).status_code for _ in range(ceiling + 1)]

    assert statuses[-1] == 429
    assert 429 not in statuses[:-1]
    limiter.reset()
