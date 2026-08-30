"""Production construction of the approved regulatory orchestrator."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.agents import AgentRegistry
from app.modules.ai.context import AuthorizedContextBuilder, ProjectAuthorizationService
from app.modules.ai.orchestration import DeterministicIntentClassifier, Orchestrator, Router
from app.modules.ai.services import AgentRunService
from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.projects.repositories import ProjectContextRepository
from app.modules.regulatory.agent import RegulatoryAgent
from app.modules.regulatory.retrieval import get_regulatory_retriever


def build_regulatory_orchestrator(session: AsyncSession) -> Orchestrator:
    repository = ProjectContextRepository(session)
    return Orchestrator(
        classifier=DeterministicIntentClassifier(),
        router=Router(AgentRegistry([
            RegulatoryAgent(
                retriever=get_regulatory_retriever(),
                provider=get_mistral_provider(),
            )
        ])),
        context_builder=AuthorizedContextBuilder(
            repository,
            ProjectAuthorizationService(repository),
        ),
        agent_run_service=AgentRunService(session),
    )
