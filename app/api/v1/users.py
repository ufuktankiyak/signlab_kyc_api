from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundException, ErrorCode
from app.core.security import require_role
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.user_service import get_user_by_id
from app.db.session import get_db

router = APIRouter()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    user = get_user_by_id(db, user_id)
    if not user:
        raise NotFoundException(
            code=ErrorCode.USER_NOT_FOUND,
            message=f"User {user_id} not found",
            details={"user_id": user_id},
        )
    return user
