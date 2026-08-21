from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from navigator.api.middleware import MaxBodySizeMiddleware
from navigator.api.rate_limit import limiter
from navigator.api.routes import conversations, health
from navigator.observability import configure_logging
from navigator.settings import get_settings

settings = get_settings()
configure_logging(settings.environment)

app = FastAPI(
    title="Clinical Care Navigator",
    description=(
        "A patient-facing clinical assistant that is allowed to refuse. "
        "Architectural demonstration on fully synthetic Synthea data. "
        "Not a medical device. Does not diagnose."
    ),
    version="0.1.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(MaxBodySizeMiddleware, max_body_bytes=settings.max_request_body_bytes)

app.include_router(health.router)
app.include_router(conversations.router)
