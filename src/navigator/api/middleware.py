"""Re-export of `zarreh_agentkit.api.middleware`.

Enforces a maximum request body size at the ASGI level (docs/PLAN.md §7
Phase 6) — this API is internet-facing, so an unbounded body is a
resource-exhaustion vector regardless of what `Content-Length` claims.
"""

from zarreh_agentkit.api.middleware import MaxBodySizeMiddleware

__all__ = ["MaxBodySizeMiddleware"]
