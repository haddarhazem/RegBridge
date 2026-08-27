import uuid
import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.observability import elapsed_ms, emit_event, metrics, set_request_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        supplied = request.headers.get("X-Request-ID")
        try:
            request_id = uuid.UUID(supplied) if supplied else uuid.uuid4()
        except (ValueError, AttributeError):
            request_id = uuid.uuid4()
        request.state.request_id = request_id
        set_request_id(str(request_id))
        started = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
            route_template = getattr(request.scope.get("route"), "path", request.url.path)
            metrics.increment("regbridge_http_requests_total", method=request.method, route_template=route_template, status=status)
            if status >= 500:
                metrics.increment("regbridge_http_errors_total", method=request.method, route_template=route_template, status="5xx")
            emit_event("http.request.completed", component="http", operation=request.method, status=status, http_method=request.method, route_template=route_template, http_status=status, duration_ms=round(elapsed_ms(started), 3))
        except Exception:
            route_template = getattr(request.scope.get("route"), "path", request.url.path)
            metrics.increment("regbridge_http_errors_total", method=request.method, route_template=route_template, status="exception")
            emit_event("http.request.failed", component="http", operation=request.method, status="error", http_method=request.method, route_template=route_template, error_code="INTERNAL_ERROR", duration_ms=round(elapsed_ms(started), 3))
            raise
        response.headers["X-Request-ID"] = str(request_id)
        return response


def get_request_id(request: Request) -> uuid.UUID:
    request_id = getattr(request.state, "request_id", None)
    if not isinstance(request_id, uuid.UUID):
        request_id = uuid.uuid4()
        request.state.request_id = request_id
    return request_id
