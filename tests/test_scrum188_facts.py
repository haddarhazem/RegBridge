import uuid

import pytest

from app.modules.ai.context import AuthorizedContextBuilder, ProjectFactProjection, ProjectContextProjection, ProjectAuthorizationService
from app.modules.projects.facts import extract_project_facts


def test_inferred_facts_are_pending_with_bounded_provenance_and_categorical_uncertainty():
    facts = extract_project_facts("Nous créons une application SaaS qui traite les données personnelles de clients en France.")
    assert facts
    assert all(fact["origin"] == "inferred" for fact in facts)
    assert all(fact["status"] == "pending_confirmation" for fact in facts)
    assert all(fact["uncertainty"] in {"high", "medium", "low"} for fact in facts)
    assert all(fact["provenance"]["source_field"] == "description" for fact in facts)
    assert all(len(fact["provenance"]["excerpt"]) <= 300 for fact in facts)


def test_negation_is_respected_and_business_coaching_is_not_generated():
    facts = extract_project_facts("Nous vendons un logiciel; il ne contient pas d'intelligence artificielle et aucun traitement de données personnelles n'est prévu.")
    values = {(fact["domain"], fact["value"]) for fact in facts}
    assert ("technology", "pas d'intelligence artificielle") in values
    assert not any("conseil" in value.lower() or "croissance" in value.lower() for _, value in values)


@pytest.mark.asyncio
async def test_context_builder_exposes_only_confirmed_project_facts():
    project_id = uuid.uuid4()

    class Repository:
        async def has_active_membership(self, requested_project_id, user_id):
            return requested_project_id == project_id

        async def load_minimal_projection(self, requested_project_id):
            return ProjectContextProjection(
                project_type="idea",
                country_code="FR",
                user_goal=None,
                facts=(ProjectFactProjection("technology", "AI", "inferred", "confirmed", {"source_field": "description", "excerpt": "AI"}, "high"),),
            )

    from app.modules.ai.contracts import OrchestrationRequest
    from app.modules.identity.schemas import AuthenticatedPrincipal

    principal = AuthenticatedPrincipal(user_id=uuid.uuid4(), email="owner@example.test", roles=(), provider="test")
    context = await AuthorizedContextBuilder(Repository(), ProjectAuthorizationService(Repository())).build(
        OrchestrationRequest(subject_type="project", subject_id=project_id, principal=principal, intent_hint="regulatory"),
        ["regulatory"],
    )
    assert context.facts[0]["status"] == "confirmed"
    assert context.facts[0]["origin"] == "inferred"
