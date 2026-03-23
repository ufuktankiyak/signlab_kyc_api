"""
Custom exception classes with standardized error codes.
All API errors should use these instead of raw HTTPException.
"""

from enum import Enum


class ErrorCode(str, Enum):
    # Auth
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    INVALID_FILE_CONTENT = "INVALID_FILE_CONTENT"
    INVALID_MRZ = "INVALID_MRZ"

    # Resource
    TRANSACTION_NOT_FOUND = "TRANSACTION_NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"

    # Processing
    OCR_TIMEOUT = "OCR_TIMEOUT"
    OCR_FAILED = "OCR_FAILED"
    IMAGE_DECODE_FAILED = "IMAGE_DECODE_FAILED"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppException(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        details: dict | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, code: ErrorCode, message: str, details: dict | None = None):
        super().__init__(code=code, message=message, status_code=404, details=details)


class AuthException(AppException):
    def __init__(self, code: ErrorCode, message: str, status_code: int = 401, details: dict | None = None):
        super().__init__(code=code, message=message, status_code=status_code, details=details)


class ValidationException(AppException):
    def __init__(self, code: ErrorCode, message: str, details: dict | None = None):
        super().__init__(code=code, message=message, status_code=422, details=details)


class FileTooLargeException(AppException):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(code=ErrorCode.FILE_TOO_LARGE, message=message, status_code=413, details=details)


class ProcessingException(AppException):
    def __init__(self, code: ErrorCode, message: str, details: dict | None = None):
        super().__init__(code=code, message=message, status_code=422, details=details)
