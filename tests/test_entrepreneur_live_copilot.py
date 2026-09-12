"""Opt-in real-service smoke test for the authenticated project Copilot.

Run locally with ENTREPRENEUR_LIVE=1. It is deliberately excluded from normal
CI because production services must never be required by automated tests.
"""

import os
import uuid
import json
import time
from pathlib import Path

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
from app.modules.projects.schemas import IdeaProjectCreate, IdeaOnboardingUpdate
from app.modules.projects.service import ProjectService
from app.modules.regulatory.orchestration import build_regulatory_orchestrator
from app.modules.regulatory.retrieval import get_regulatory_retriever
from app.modules.ai.providers.selection import get_llm_provider


pytestmark = pytest.mark.skipif(
    os.getenv("ENTREPRENEUR_LIVE") != "1",
    reason="set ENTREPRENEUR_LIVE=1 to call real Qdrant, BGE-M3, and the configured LLM service",
)


@pytest.mark.asyncio
async def test_real_project_copilot_uses_authorized_context_and_persists_public_answer(monkeypatch) -> None:
    factory = get_session_factory()
    user_id = uuid.uuid4()
    email = f"entrepreneur-live-{user_id}@example.test"
    principal = AuthenticatedPrincipal(user_id=user_id, email=email, roles=("entrepreneur",), provider="live-smoke")
    project_id: uuid.UUID | None = None
    thread_id: uuid.UUID | None = None
    observations = {'synthetic_only': True, 'evidence': [], 'calls': []}

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
            await ProjectService(session).update_onboarding(principal, project_id, IdeaOnboardingUpdate(
                activity='EnerSight : plateforme SaaS de suivi et optimisation énergétique pour les PME.',
                sector='Efficacité énergétique', technology='Analyse de données et intelligence artificielle',
                data='Factures énergétiques, données de compteurs, coordonnées professionnelles des utilisateurs.',
                target_market='PME françaises', location='France',
                confirm=['activity', 'sector', 'technology', 'data', 'market', 'location'],
            ))
            conversations = ConversationService(session)
            thread = await conversations.create_thread(principal, title="Smoke Copilot", subject_type="project", subject_id=project_id)
            thread_id = thread.id
            orchestrator = build_regulatory_orchestrator(session)
            retriever = get_regulatory_retriever()
            retrieve = retriever.retrieve
            provider = get_llm_provider()
            generate = provider.generate
            observations['starting_collection_count'] = retriever.client.count(retriever.collection, exact=True).count

            async def record_retrieval(question):
                result = await retrieve(question)
                observations['evidence'] = [item.model_dump() for item in result]
                return result

            async def record_generation(request):
                call = {'operation': request.operation, 'max_tokens': request.max_tokens}
                observations['calls'].append(call)
                try:
                    result = await generate(request)
                    call.update({'model': result.model, 'usage': result.usage, 'execution': result.execution.model_dump() if result.execution else None})
                    return result
                except Exception as error:
                    call.update({'error_type': type(error).__name__, 'category': getattr(error, 'category', None), 'http_status': getattr(error, 'http_status', None), 'usage': getattr(error, 'usage', {})})
                    raise

            monkeypatch.setattr(retriever, 'retrieve', record_retrieval)
            monkeypatch.setattr(provider, 'generate', record_generation)
            started = time.perf_counter()
            turn = await ProjectCopilotService(conversations, orchestrator).respond(
                principal,
                thread.id,
                "Quelles sont les principales obligations réglementaires que je dois prendre en compte pour EnerSight concernant les données personnelles, l'intelligence artificielle et la sécurité de ma plateforme SaaS en France ?",
            )
            assert turn.assistant_message.content
            runs = list((await session.scalars(select(AgentRun).where(AgentRun.subject_id == project_id))).all())
            regulatory_run = next((run for run in runs if run.capability == "regulatory"), None)
            safe_diagnostic = {
                key: (regulatory_run.response_payload or {}).get('result', {}).get(key)
                for key in (
                    "verification_verdict",
                    "verification_failure_category",
                    "structural_issue_count",
                    "semantic_claim_count",
                    "generation_provider",
                    "generation_model",
                    "verification_provider",
                    "verification_model",
                )
            } if regulatory_run is not None else {"regulatory_run": "missing"}
            artifact = {
                'synthetic_only': True, 'answer': turn.assistant_message.content,
                'sources': turn.sources, 'warnings': turn.warnings,
                'seconds': round(time.perf_counter() - started, 3),
                'verification': safe_diagnostic,
                'runs': [{'id': str(run.id), 'request_id': str(run.request_id), 'parent_run_id': str(run.parent_run_id) if run.parent_run_id else None,
                          'status': run.status, 'capability': run.capability, 'response': run.response_payload} for run in runs],
            }
            Path('artifacts/browser-e2e').mkdir(parents=True, exist_ok=True)
            Path('artifacts/browser-e2e/recovery-direct.json').write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'direct_seconds': artifact['seconds'], 'sources': turn.sources, 'verification': safe_diagnostic}))
            assert turn.sources, f"Copilot returned no public sources: {safe_diagnostic}"
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
                runs = (await session.scalars(select(AgentRun).where(AgentRun.subject_id == project_id))).all()
                observations['traces'] = [{'status': run.status, 'capability': run.capability, 'error_code': run.error_code, 'response': run.response_payload} for run in runs]
            if 'starting_collection_count' in observations:
                observations['ending_collection_count'] = retriever.client.count(retriever.collection, exact=True).count
            Path('artifacts/browser-e2e').mkdir(parents=True, exist_ok=True)
            Path('artifacts/browser-e2e/recovery-direct-observations.json').write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'evidence_count': len(observations['evidence']), 'calls': observations['calls'], 'traces': observations.get('traces')}))
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
