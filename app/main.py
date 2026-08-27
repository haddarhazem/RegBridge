import logging

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.request_id import RequestIdMiddleware
from app.db import models as _models  # noqa: F401 - register all ORM models deterministically
from app.modules.ai.router import router as conversations_router
from app.modules.identity.router import router as identity_router
from app.modules.projects.router import router as projects_router
from app.modules.documents.router import router as documents_router
from app.modules.regulatory.router import router as regulatory_router
from app.modules.regulatory.assessment_router import router as assessment_router
from app.modules.regulatory.roadmap_router import router as roadmap_router
from app.modules.compliance.router import router as compliance_router
from app.modules.sharing.router import router as sharing_router
from app.modules.investment.router import router as investment_router
from app.modules.investment.opportunity_router import router as opportunity_router
from app.modules.projects.search_router import router as startup_search_router
from app.modules.events.router import router as events_router
from app.modules.network.router import router as network_router
from app.modules.investment.matching_router import router as matching_router
from app.modules.investment.brief_router import router as brief_router
from app.modules.research.router import router as research_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    active_settings = settings or get_settings()
    application = FastAPI(title=active_settings.app_name)
    application.add_middleware(RequestIdMiddleware)
    application.include_router(health_router)
    application.include_router(metrics_router)
    application.include_router(identity_router)
    application.include_router(projects_router)
    application.include_router(documents_router)
    application.include_router(conversations_router)
    application.include_router(regulatory_router)
    application.include_router(assessment_router)
    application.include_router(roadmap_router)
    application.include_router(compliance_router)
    application.include_router(sharing_router)
    application.include_router(investment_router)
    application.include_router(opportunity_router)
    application.include_router(startup_search_router)
    application.include_router(events_router)
    application.include_router(network_router)
    application.include_router(matching_router)
    application.include_router(brief_router)
    application.include_router(research_router)
    logger.info("Starting %s in %s environment", active_settings.app_name, active_settings.environment)
    return application


app = create_app()
