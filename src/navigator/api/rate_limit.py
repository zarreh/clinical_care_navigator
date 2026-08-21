"""Single shared `Limiter` instance — defined separately from `main.py` so route
modules can apply `@limiter.limit(...)` to individual endpoints without a
circular import.

Applied per-route via the decorator rather than `SlowAPIMiddleware`: the
middleware resolves a request's handler by walking `app.routes` for plain
`APIRoute` objects with `.endpoint`, but FastAPI's `include_router` wraps
included routers in an internal mount object that has no `.endpoint`, so it
finds no handler and treats every route as exempt.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from navigator.settings import get_settings

limiter = Limiter(key_func=get_remote_address)
DEFAULT_RATE_LIMIT = f"{get_settings().rate_limit_per_minute}/minute"
