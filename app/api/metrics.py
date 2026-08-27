from fastapi import APIRouter

from app.core.observability import metrics

router = APIRouter()


@router.get("/metrics")
async def operational_metrics() -> dict:
    """Return bounded operational aggregates without application data."""
    return metrics.snapshot()
