"""
Global exception handlers — registered in main.py.
All error responses follow the standard ErrorResponse schema.
"""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.exceptions import AppException, ErrorCode
from app.core.request_context import request_id_var

logger = logging.getLogger("signlab.errors")


def _request_id() -> str | None:
    try:
        return request_id_var.get()
    except LookupError:
        return None


def _error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "request_id": _request_id(),
    }


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code.value, exc.message, exc.details),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    field_errors = {}
    for err in exc.errors():
        loc = ".".join(str(l) for l in err["loc"] if l != "body")
        field_errors[loc] = err["msg"]

    return JSONResponse(
        status_code=422,
        content=_error_body(
            ErrorCode.VALIDATION_ERROR.value,
            "Request validation failed",
            {"fields": field_errors},
        ),
    )


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = getattr(exc, "retry_after", None)
    headers = {"Retry-After": str(retry_after)} if retry_after else {}
    return JSONResponse(
        status_code=429,
        content=_error_body(
            ErrorCode.RATE_LIMIT_EXCEEDED.value,
            f"Rate limit exceeded: {exc.detail}",
        ),
        headers=headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception",
        extra={"request_id": _request_id(), "path": request.url.path},
    )
    return JSONResponse(
        status_code=500,
        content=_error_body(
            ErrorCode.INTERNAL_ERROR.value,
            "An internal error occurred. Please try again later.",
        ),
    )
