import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        supplied = request.headers.get("X-Request-ID")
        try:
            request_id = uuid.UUID(supplied) if supplied else uuid.uuid4()
        except (ValueError, AttributeError):
            request_id = uuid.uuid4()
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = str(request_id)
        return response


def get_request_id(request: Request) -> uuid.UUID:
    request_id = getattr(request.state, "request_id", None)
    if not isinstance(request_id, uuid.UUID):
        request_id = uuid.uuid4()
        request.state.request_id = request_id
    return request_id
