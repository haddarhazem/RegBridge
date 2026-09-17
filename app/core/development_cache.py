"""Development-only cache policy for the combined static frontend runtime."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class DevelopmentStaticNoStoreMiddleware(BaseHTTPMiddleware):
    """Prevent a demo browser from retaining stale local frontend assets."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if request.method == "GET" and response.status_code < 400 and (
            path.startswith(("/entrepreneur/", "/auth/"))
            or path in {"/", "/styles.css"}
        ):
            response.headers["Cache-Control"] = "no-store"
        return response
