from zarreh_agentkit.api.health import build_health_router

from navigator.api.rate_limit import READ_RATE_LIMIT, limiter

router = build_health_router(limiter, READ_RATE_LIMIT)
