import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppException, AuthException, ErrorCode
from app.core.rate_limit import limiter
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import RegisterRequest, LoginRequest, TokenResponse, UserResponse
from app.services import audit_service

logger = logging.getLogger(__name__)
router = APIRouter()
_settings = get_settings()


@router.post("/register", response_model=UserResponse, status_code=201, summary="Register a new user")
@limiter.limit(_settings.RATE_LIMIT_AUTH)
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise AppException(
            code=ErrorCode.EMAIL_ALREADY_EXISTS,
            message="Email already registered",
            status_code=409,
        )
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    audit_service.log_event(
        db, "auth.register",
        actor_id=user.id,
        actor_email=user.email,
        resource_type="user",
        resource_id=str(user.id),
    )
    return user


@router.post("/login", response_model=TokenResponse, summary="Login and get access token")
@limiter.limit(_settings.RATE_LIMIT_AUTH)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        audit_service.log_event(
            db, "auth.login_failed",
            actor_email=body.email,
            detail={"reason": "invalid_credentials"},
        )
        raise AuthException(
            code=ErrorCode.INVALID_CREDENTIALS,
            message="Invalid email or password",
        )
    if not user.is_active:
        audit_service.log_event(
            db, "auth.login_failed",
            actor_id=user.id,
            actor_email=user.email,
            detail={"reason": "account_deactivated"},
        )
        raise AuthException(
            code=ErrorCode.ACCOUNT_DEACTIVATED,
            message="Account is deactivated",
            status_code=403,
        )

    token = create_access_token(user.id, user.role)

    audit_service.log_event(
        db, "auth.login",
        actor_id=user.id,
        actor_email=user.email,
        resource_type="user",
        resource_id=str(user.id),
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse, summary="Get current user info")
def me(current_user: User = Depends(get_current_user)):
    return current_user
