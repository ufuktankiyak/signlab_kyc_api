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

    # LOGGING
    LOG_LEVEL: str = "INFO"

    # ELASTICSEARCH (business logs)
    ELASTICSEARCH_URL: str = "http://127.0.0.1:9200"
    ELASTICSEARCH_INDEX: str = "signlab-business-logs"
    ELASTICSEARCH_ENABLED: bool = False

    # RATE LIMITING
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_OCR: str = "10/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"

    # FILE SIZE LIMITS (bytes)
    MAX_IMAGE_SIZE: int = 10 * 1024 * 1024    # 10 MB
    MAX_VIDEO_SIZE: int = 50 * 1024 * 1024    # 50 MB

    # STORAGE
    STORAGE_PATH: str = "/app/storage"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
