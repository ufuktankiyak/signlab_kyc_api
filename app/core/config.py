from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # APP
    APP_NAME: str = "Signlab KYC API"
    ENV: str = "local"
    DEBUG: bool = True
    APP_VERSION: str = "1.0.0"

    # API
    API_V1_PREFIX: str = "/api/v1"

    # SECURITY
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # DATABASE
    DATABASE_URL: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
