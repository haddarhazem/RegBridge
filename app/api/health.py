import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.db.session import check_database

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    try:
        await check_database()
    except Exception:
        logger.exception("Database health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "unavailable"},
        )
    return JSONResponse(status_code=200, content={"status": "ok", "database": "ok"})
