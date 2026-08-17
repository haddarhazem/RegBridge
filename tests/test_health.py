from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_health_when_database_is_available() -> None:
    with patch("app.api.health.check_database", new=AsyncMock()):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.asyncio
async def test_health_when_database_is_unavailable() -> None:
    with patch("app.api.health.check_database", new=AsyncMock(side_effect=RuntimeError("unavailable"))):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}
