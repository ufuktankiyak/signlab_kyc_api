from fastapi import FastAPI
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.models.user import User
import app.models.kyc  # noqa: F401 — registers KYC models with SQLAlchemy metadata

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == "admin@signlab.com").first():
            db.add(User(
                email="admin@signlab.com",
                password_hash=hash_password("changeme123"),
                role="admin",
            ))
            db.commit()
    finally:
        db.close()
