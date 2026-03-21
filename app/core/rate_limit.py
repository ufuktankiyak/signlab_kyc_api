from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import get_settings


def _key_func(request: Request) -> str:
    """Rate limit by JWT subject (user id) if authenticated, otherwise by IP."""
    # If auth has been resolved, use user id for fairer per-user limiting
    user = getattr(request.state, "current_user", None)
    if user is not None:
        return f"user:{user.id}"
    return get_remote_address(request)


settings = get_settings()

limiter = Limiter(
    key_func=_key_func,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    storage_uri="memory://",
)
