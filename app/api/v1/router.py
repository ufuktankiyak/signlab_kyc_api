from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as user_router
from app.api.v1.documents import router as document_router
from app.api.v1.kyc import router as kyc_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_router.include_router(user_router, prefix="/users", tags=["Users"])
api_router.include_router(document_router, prefix="/documents", tags=["Documents"])
api_router.include_router(kyc_router, prefix="/kyc", tags=["KYC"])
