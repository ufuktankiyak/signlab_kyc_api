from enum import Enum

from pydantic import BaseModel, EmailStr, field_validator, Field


class UserRole(str, Enum):
    admin = "admin"
    operator = "operator"


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_active: bool


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = UserRole.operator

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if v.isdigit() or v.isalpha():
            raise ValueError("Password must contain both letters and numbers")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
