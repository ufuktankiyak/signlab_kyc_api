import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_context import request_id_var, client_ip_var

logger = logging.getLogger("signlab.request")


def _get_client_ip(request: Request) -> str | None:
    """Extract client IP — trust X-Forwarded-For / X-Real-IP from internal network."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid4().hex[:12]
        request.state.request_id = request_id

        ip = _get_client_ip(request)

        # Set context vars so services can read them without parameter passing
        req_token = request_id_var.set(request_id)
        ip_token = client_ip_var.set(ip)

        start = time.time()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(req_token)
            client_ip_var.reset(ip_token)

        duration_ms = round((time.time() - start) * 1000, 2)

        status = response.status_code
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status,
            "duration_ms": duration_ms,
            "client_ip": ip,
        }

        if status >= 500:
            logger.error("request completed", extra=log_data)
        elif status >= 400:
            logger.warning("request completed", extra=log_data)
        else:
            logger.info("request completed", extra=log_data)

        response.headers["X-Request-ID"] = request_id
        return response
