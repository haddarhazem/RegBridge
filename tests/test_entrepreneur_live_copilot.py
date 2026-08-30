"""Opt-in real-service smoke test for the authenticated project Copilot.

Run locally with ENTREPRENEUR_LIVE=1. It is deliberately excluded from normal
CI because production services must never be required by automated tests.
"""

import os
import uuid

import pytest
from sqlalchemy import delete, select

from app.db.session import get_session_factory
from app.modules.ai.copilot import ProjectCopilotService
from app.modules.ai.models import AgentRun, ConversationMessage, ConversationThread
from app.modules.ai.services import ConversationService
from app.modules.audit import AuditLog
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectFact, ProjectMember
from app.modules.projects.schemas import IdeaProjectCreate
from app.modules.projects.service import ProjectService
from app.modules.regulatory.orchestration import build_regulatory_orchestrator


pytestmark = pytest.mark.skipif(
    os.getenv("ENTREPRENEUR_LIVE") != "1",
    reason="set ENTREPRENEUR_LIVE=1 to call real Qdrant, BGE-M3, and Mistral services",
)


@pytest.mark.asyncio
async def test_real_project_copilot_uses_authorized_context_and_persists_public_answer() -> None:
    factory = get_session_factory()
    user_id = uuid.uuid4()
    email = f"entrepreneur-live-{user_id}@example.test"
    principal = AuthenticatedPrincipal(user_id=user_id, email=email, roles=("entrepreneur",), provider="live-smoke")
    project_id: uuid.UUID | None = None
    thread_id: uuid.UUID | None = None

    try:
        async with factory() as session:
            session.add(User(id=user_id, email=email))
            await session.commit()
            project = await ProjectService(session).create_idea(principal, IdeaProjectCreate(display_name="Smoke RGPD"))
            project_id = project.id
            project.raw_description = "Plateforme SaaS française traitant les coordonnées de clients professionnels."
            session.add(ProjectFact(
                project_id=project.id,
                domain="data",
                value="coordonnées de clients professionnels",
                origin="inferred",
                status="confirmed",
                provenance={"source_field": "description", "excerpt": "coordonnées de clients professionnels"},
                uncertainty="low",
            ))
            await session.commit()

        async with factory() as session:
            conversations = ConversationService(session)
            thread = await conversations.create_thread(principal, title="Smoke Copilot", subject_type="project", subject_id=project_id)
            thread_id = thread.id
            turn = await ProjectCopilotService(conversations, build_regulatory_orchestrator(session)).respond(
                principal,
                thread.id,
                "Quelles obligations principales dois-je considérer pour traiter les coordonnées de mes clients ?",
            )
            assert turn.assistant_message.content
            assert turn.sources
            assert turn.assistant_message.content_json["sources"] == turn.sources
            assert all("point_id" not in source and "score" not in source.lower() for source in turn.sources)

        async with factory() as session:
            persisted = await ConversationService(session).get_thread(principal, thread_id)
            assert [message.role for message in persisted.messages] == ["user", "assistant"]
            runs = list((await session.scalars(select(AgentRun).where(AgentRun.subject_id == project_id))).all())
            assert len(runs) >= 2
    finally:
        async with factory() as session:
            if project_id is not None:
                await session.execute(delete(AgentRun).where(AgentRun.subject_id == project_id))
            if thread_id is not None:
                await session.execute(delete(ConversationMessage).where(ConversationMessage.thread_id == thread_id))
                await session.execute(delete(ConversationThread).where(ConversationThread.id == thread_id))
            if project_id is not None:
                await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
                await session.execute(delete(ProjectFact).where(ProjectFact.project_id == project_id))
                await session.execute(delete(ProjectMember).where(ProjectMember.project_id == project_id))
                await session.execute(delete(Project).where(Project.id == project_id))
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()
