import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.ai.llm import LLMProvider, LLMProviderError
from app.modules.ai.providers.mistral import get_mistral_provider
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.investment.matching_schemas import MatchingCreate, MatchingRunResponse
from app.modules.investment.matching_service import MatchingService

router = APIRouter(prefix="/investment-matches", tags=["investment-matching"])
Session = Annotated[AsyncSession, Depends(get_session)]
Principal = Annotated[AuthenticatedPrincipal, Depends(get_authenticated_principal)]


def get_optional_matching_provider() -> LLMProvider | None:
    try:
        return get_mistral_provider()
    except LLMProviderError:
        return None


Provider = Annotated[LLMProvider | None, Depends(get_optional_matching_provider)]


@router.post("", response_model=MatchingRunResponse, status_code=status.HTTP_201_CREATED)
async def create_matching(data: MatchingCreate, principal: Principal, session: Session, provider: Provider):
    return await MatchingService(session, provider).create(principal, data.startup_project_id, data.investor_thesis_version_id)


@router.get("/{run_id}", response_model=MatchingRunResponse)
async def get_matching(run_id: uuid.UUID, principal: Principal, session: Session):
    return await MatchingService(session).get(principal, run_id)
