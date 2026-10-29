"""Single shared `Limiter` instance — defined separately from `main.py` so route
modules can apply `@limiter.limit(...)` to individual endpoints without a
circular import.

Built on `zarreh_agentkit.api.rate_limit`. Applied per-route via the decorator
rather than `SlowAPIMiddleware`, which treats `include_router` routes as exempt.

Two ceilings: `WRITE_RATE_LIMIT` on routes that start or resume an LLM run (they
cost money), `READ_RATE_LIMIT` on reads and the SSE replay (one page view makes
several). Each decorated route counts against its own per-IP bucket.
"""

from zarreh_agentkit.api.rate_limit import build_limiter

from navigator.settings import get_settings

limiter = build_limiter()
WRITE_RATE_LIMIT = f"{get_settings().write_rate_limit_per_minute}/minute"
READ_RATE_LIMIT = f"{get_settings().read_rate_limit_per_minute}/minute"
