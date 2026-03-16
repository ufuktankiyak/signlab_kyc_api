from fastapi import APIRouter
from app.api.v1.users import router as user_router
from app.api.v1.documents import router as document_router

api_router = APIRouter()
api_router.include_router(user_router, prefix="/users", tags=["Users"])
api_router.include_router(document_router, prefix="/documents", tags=["Documents"])
