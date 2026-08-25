"""Exit criterion (c): the per-client rate limit is demonstrably enforced
(docs/PLAN.md §7 Phase 6, §5.6). Uses the walking-skeleton stream endpoint —
also rate-limited — so the limit is proven without spinning the real graph."""

from __future__ import annotations

from fastapi.testclient import TestClient

from navigator.api.main import app
from navigator.api.rate_limit import limiter
from navigator.settings import get_settings


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
