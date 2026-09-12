"""Opt-in read-only audit of the named local EnerSight project; no content logged."""
import hashlib
import json
import os

import pytest
from sqlalchemy import select

from app.db.session import get_session_factory
from app.modules.ai.context import AuthorizedContextBuilder, ProjectAuthorizationService
from app.modules.ai.contracts import OrchestrationRequest
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project
from app.modules.projects.repositories import ProjectContextRepository
from app.modules.projects.router import project_response


@pytest.mark.skipif(os.getenv('ENTREPRENEUR_CONTEXT_AUDIT') != '1', reason='Local read-only context audit is opt-in')
@pytest.mark.asyncio
async def test_persisted_enersight_context_projection():
    async with get_session_factory()() as session:
        projects = (await session.scalars(select(Project).where(Project.display_name == 'EnerSight'))).all()
        assert projects, 'EnerSight project not found in configured database'
        complete_projects = 0
        for project in projects:
            repository = ProjectContextRepository(session)
            principal = AuthenticatedPrincipal(user_id=project.owner_user_id, email='local-audit@example.test', roles=('entrepreneur',), provider='local-read-only-audit')
            context = await AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository)).build(
                OrchestrationRequest(principal=principal, subject_type='project', subject_id=project.id, intent_hint='regulatory', question='Contexte réglementaire'), ['regulatory'],
            )
            response = project_response(project, True)
            fields = [('activity', 'activity', 'activity'), ('sector', 'sector', 'sector'), ('technology', 'technology', 'technology'),
                      ('data', 'data_context', 'data'), ('market', 'target_market', 'target_market'), ('location', 'location', 'location')]
            result = {}
            for domain, attribute, api_field in fields:
                value = getattr(project, attribute)
                result[domain] = {'confirmed': domain in response.confirmed_fields, 'length': len(value or ''),
                                  'api_exact': getattr(response, api_field) == value, 'context_exact': getattr(context, attribute) == value}
                if domain in response.confirmed_fields:
                    assert bool(value) and result[domain]['api_exact'] and result[domain]['context_exact'], f'{domain}: confirmed projection mismatch'
            complete_projects += len(response.confirmed_fields) == 6
            assert len(context.data_context or '') <= 2000
            print(json.dumps({'project': 'EnerSight', 'fields': result, 'confirmed_count': len(response.confirmed_fields),
                              'data_sha256': hashlib.sha256((context.data_context or '').encode()).hexdigest(), 'documents_in_context': context.document is not None}))
        assert complete_projects, 'No EnerSight project has six confirmed fields in the configured database'
