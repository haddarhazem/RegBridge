from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.observability import dependency_result, elapsed_ms
import time


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


async def check_database() -> None:
    """Execute a real lightweight query to verify PostgreSQL connectivity."""
    started = time.perf_counter()
    try:
        async with get_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        dependency_result(dependency="postgresql", operation="health_check", status="error", duration_ms=elapsed_ms(started), error_category="DEPENDENCY_UNAVAILABLE")
        raise
    dependency_result(dependency="postgresql", operation="health_check", status="ok", duration_ms=elapsed_ms(started))
