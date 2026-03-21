import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("signlab.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = uuid4().hex[:12]
        request.state.request_id = request_id

        start = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start) * 1000, 2)

        status = response.status_code
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": status,
            "duration_ms": duration_ms,
            "client_ip": request.client.host if request.client else None,
        }

        if status >= 500:
            logger.error("request completed", extra=log_data)
        elif status >= 400:
            logger.warning("request completed", extra=log_data)
        else:
            logger.info("request completed", extra=log_data)

        response.headers["X-Request-ID"] = request_id
        return response
