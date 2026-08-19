import logging

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.request_id import RequestIdMiddleware
from app.modules.ai.router import router as conversations_router
from app.modules.identity.router import router as identity_router
from app.modules.projects.router import router as projects_router
from app.modules.documents.router import router as documents_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    active_settings = settings or get_settings()
    application = FastAPI(title=active_settings.app_name)
    application.add_middleware(RequestIdMiddleware)
    application.include_router(health_router)
    application.include_router(identity_router)
    application.include_router(projects_router)
    application.include_router(documents_router)
    application.include_router(conversations_router)
    logger.info("Starting %s in %s environment", active_settings.app_name, active_settings.environment)
    return application


app = create_app()
