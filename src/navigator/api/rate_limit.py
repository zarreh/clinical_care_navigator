"""Single shared `Limiter` instance — defined separately from `main.py` so route
modules can apply `@limiter.limit(...)` to individual endpoints without a
circular import.

Built on `zarreh_agentkit.api.rate_limit`. Applied per-route via the decorator
rather than `SlowAPIMiddleware`, which treats `include_router` routes as exempt.
"""

from zarreh_agentkit.api.rate_limit import build_limiter, default_rate_limit

from navigator.settings import get_settings

limiter = build_limiter()
DEFAULT_RATE_LIMIT = default_rate_limit(get_settings())
