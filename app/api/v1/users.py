from fastapi import APIRouter
from app.schemas.user import UserResponse

router = APIRouter()

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int):
    return {
        "id": user_id,
        "email": "test@mail.com"
    }
