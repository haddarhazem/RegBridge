from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.session import check_database
from app.core.observability import emit_event

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    try:
        await check_database()
    except Exception:
        emit_event("health.database.failed", component="postgresql", operation="health_check", status="error", error_code="DEPENDENCY_UNAVAILABLE")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable"},
        )
    return JSONResponse(status_code=200, content={"status": "ok", "database": "ok"})
