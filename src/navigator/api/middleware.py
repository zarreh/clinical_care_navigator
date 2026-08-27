"""`MaxBodySizeMiddleware` is provided by `zarreh_agentkit.api.middleware`
(extracted substrate); this module re-exports it so existing
`navigator.api.middleware` imports keep working."""

from zarreh_agentkit.api.middleware import MaxBodySizeMiddleware

__all__ = ["MaxBodySizeMiddleware"]
