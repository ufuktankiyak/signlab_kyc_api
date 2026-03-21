import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.models.user import User

settings = get_settings()
setup_logging(
    settings.ENV,
    settings.LOG_LEVEL,
    es_url=settings.ELASTICSEARCH_URL,
    es_index=settings.ELASTICSEARCH_INDEX,
    es_enabled=settings.ELASTICSEARCH_ENABLED,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestLoggingMiddleware)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.on_event("startup")
def startup():
    logger.info("Application starting", extra={"env": settings.ENV})
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == "admin@signlab.com").first():
            db.add(User(
                email="admin@signlab.com",
                password_hash=hash_password("changeme123"),
                role="admin",
            ))
            db.commit()
            logger.info("Admin seed user created")
    finally:
        db.close()
