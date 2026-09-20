import uuid
from time import perf_counter

import pytest

from app.modules.ai.context import AuthorizedContextBuilder, ProjectAuthorizationService, ProjectContextProjection
from app.modules.ai.contracts import AgentRequest, AuthorizedContext, OrchestrationRequest
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.knowledge_graph import (
    GraphContextProvider,
    GraphDocumentProjection,
    GraphFactProjection,
    GraphRegulatoryAssessmentProjection,
    KnowledgeRelation,
    KnowledgeNodeType,
    ProjectKnowledgeGraphAccessDenied,
    ProjectKnowledgeGraphBuilder,
    ProjectKnowledgeGraphProjection,
    ProjectKnowledgeGraphService,
)
from app.modules.projects.knowledge_enrichment import ProjectKnowledgeCandidateExtractor, normalize_concept_key
from app.modules.regulatory.agent import RegulatoryAgent


def projection(*, facts=(), sector="Services", technology="Application web", data="Données personnelles", market="PME", location="Europe", business_model=None, regulatory_assessment=None):
    return ProjectKnowledgeGraphProjection(
        project_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        display_name="Projet de test",
        project_type="idea",
        country_code="FR",
        activity=None,
        sector=sector,
        technology=technology,
        data_context=data,
        target_market=market,
        location=location,
        confirmed_fields=frozenset({"sector", "technology", "data", "market", "location"}),
        business_model=business_model,
        facts=tuple(facts),
        documents=(GraphDocumentProjection(uuid.UUID("00000000-0000-0000-0000-000000000002"), "Plan", "pdf", "confidential", "private"),),
        regulatory_assessment=regulatory_assessment,
    )


def test_graph_is_deterministic_deduplicated_and_has_safe_document_metadata():
    source = projection(facts=(GraphFactProjection("technology", "Application web", "confirmed", "inferred"),))
    first = ProjectKnowledgeGraphBuilder().build(source)
    second = ProjectKnowledgeGraphBuilder().build(source)

    assert first == second
    assert len([node for node in first.nodes if node.type == KnowledgeNodeType.TECHNOLOGY]) == 1
    document = next(node for node in first.nodes if node.type == KnowledgeNodeType.DOCUMENT)
    assert document.properties == {"document_type": "pdf", "classification": "confidential", "visibility": "private"}
    assert "extracted_text" not in document.model_dump_json()


def test_pending_and_deleted_facts_never_enter_trusted_graph():
    graph = ProjectKnowledgeGraphBuilder().build(projection(
        facts=(
            GraphFactProjection("sector", "Pending sector", "pending_confirmation", "inferred"),
            GraphFactProjection("technology", "Deleted technology", "deleted", "inferred"),
            GraphFactProjection("data", "Confirmed category", "confirmed", "user_declared"),
        ),
    ))
    labels = {node.label for node in graph.nodes}
    assert "Pending sector" not in labels
    assert "Deleted technology" not in labels
    assert "Confirmed category" in labels


def test_rejected_stale_sector_and_future_location_facts_are_excluded_from_graph_and_context():
    graph = ProjectKnowledgeGraphBuilder().build(projection(
        sector="EnergyTech / SaaS B2B",
        location="Île-de-France, France",
        facts=(
            GraphFactProjection("sector", "logiciel B2B", "deleted", "inferred", uuid.uuid4(), {"source_field": "description"}),
            GraphFactProjection("location", "Union européenne", "deleted", "inferred", uuid.uuid4(), {"source_field": "description"}),
        ),
    ))
    labels = {node.label for node in graph.nodes}
    assert "logiciel B2B" not in labels
    assert "Union européenne" not in labels
    assert "EnergyTech / SaaS B2B" in labels
    assert "Île-de-France, France" in labels
    context = GraphContextProvider().select(graph, "Dans quelle zone géographique mon projet opère-t-il actuellement ?")
    assert "Union européenne" not in {node.label for node in context.nodes}
    assert "Île-de-France, France" in {node.label for node in context.nodes}


def test_graph_evolves_only_with_current_confirmed_facts_and_is_generic():
    builder = ProjectKnowledgeGraphBuilder()
    initial = builder.build(projection(sector=None, technology=None, data=None, market="Professionnels", location="Belgique"))
    evolved = builder.build(projection(
        sector=None, technology=None, data=None, market="Professionnels", location="Belgique",
        facts=(GraphFactProjection("technology", "Téléconsultation", "corrected", "user_declared"),),
    ))
    assert len(evolved.nodes) == len(initial.nodes) + 1
    assert any(node.label == "Téléconsultation" for node in evolved.nodes)
    assert all("EnerSight" not in node.label and "IoT" not in node.label for node in evolved.nodes)


def test_long_canonical_profile_value_is_a_single_bounded_deterministic_node():
    long_value = "donnée confirmée " * 80
    graph = ProjectKnowledgeGraphBuilder().build(projection(data=long_value))
    node = next(item for item in graph.nodes if item.type == KnowledgeNodeType.DATA_CATEGORY)
    assert len(node.label) <= 240
    assert node.label.endswith("…")
    assert node.properties["display_value_truncated"] is True


def test_graph_context_is_bounded_and_question_targeted():
    graph = ProjectKnowledgeGraphBuilder().build(projection())
    context = GraphContextProvider().select(graph, "Quelles données personnelles mon projet traite-t-il ?")
    assert len(context.nodes) <= GraphContextProvider.max_nodes
    assert len(context.edges) <= GraphContextProvider.max_edges
    assert context.max_depth == 2
    assert any(node.type == KnowledgeNodeType.DATA_CATEGORY for node in context.nodes)
    assert all(node.type in {KnowledgeNodeType.PROJECT, KnowledgeNodeType.DATA_CATEGORY} for node in context.nodes)


@pytest.mark.asyncio
async def test_context_builder_adds_only_trusted_bounded_graph_after_authorization():
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()

    class Repository:
        async def has_active_membership(self, received_project_id, received_user_id):
            return received_project_id == project_id and received_user_id == user_id

        async def load_minimal_projection(self, _project_id):
            return ProjectContextProjection("idea", "FR", None)

        async def load_knowledge_graph_projection(self, _project_id):
            return projection(facts=(GraphFactProjection("data", "Donnée confirmée", "confirmed", "user_declared"),))

    request = OrchestrationRequest(
        principal=AuthenticatedPrincipal(user_id=user_id, email="owner@example.test", roles=("entrepreneur",), provider="test"),
        subject_type="project", subject_id=project_id, question="Quelles données mon projet traite-t-il ?", intent_hint="regulatory",
    )
    context = await AuthorizedContextBuilder(Repository(), ProjectAuthorizationService(Repository())).build(request, ["regulatory"])
    assert context.graph_context is not None
    assert len(context.graph_context.nodes) <= GraphContextProvider.max_nodes
    assert all(node.trust_status.value in {"CONFIRMED", "VERIFIED"} for node in context.graph_context.nodes)


@pytest.mark.asyncio
async def test_confirmed_provider_reaches_trusted_context_and_answers_without_regulatory_retrieval():
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()

    class Repository:
        async def has_active_membership(self, received_project_id, received_user_id):
            return received_project_id == project_id and received_user_id == user_id

        async def load_minimal_projection(self, _project_id):
            return ProjectContextProjection("idea", "FR", None)

        async def load_knowledge_graph_projection(self, _project_id):
            return projection(
                technology=None,
                facts=(GraphFactProjection("provider", "OVHcloud", "confirmed", "inferred", uuid.uuid4(), {"source_field": "copilot_message"}),),
            )

    orchestration_request = OrchestrationRequest(
        principal=AuthenticatedPrincipal(user_id=user_id, email="owner@example.test", roles=("entrepreneur",), provider="test"),
        subject_type="project", subject_id=project_id,
        question="Quel fournisseur cloud utilise mon projet ?", intent_hint="regulatory",
    )
    context = await AuthorizedContextBuilder(Repository(), ProjectAuthorizationService(Repository())).build(orchestration_request, ["regulatory"])
    assert context.graph_context is not None
    assert any(node.type == KnowledgeNodeType.PROVIDER and node.label == "OVHcloud" for node in context.graph_context.nodes)

    class MustNotRetrieve:
        calls = 0

        async def retrieve(self, _question):
            self.calls += 1
            raise AssertionError("A confirmed project-fact question must not use regulatory retrieval")

    class MustNotGenerate:
        calls = 0

        async def generate(self, _request):
            self.calls += 1
            raise AssertionError("A confirmed project-fact question must not use an LLM")

    retriever, provider = MustNotRetrieve(), MustNotGenerate()
    result = await RegulatoryAgent(retriever=retriever, provider=provider).run(AgentRequest(
        request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(), question=orchestration_request.question,
        capability="regulatory", locale="fr", subject_type="project", subject_id=project_id,
        authorized_context=context,
    ))
    assert result.answer == "Votre projet utilise OVHcloud comme fournisseur d’hébergement."
    assert result.structured_payload["answer_source"] == "PROJECT_GRAPH"
    assert result.structured_payload["regulatory_retrieval_skipped"] is True
    assert retriever.calls == 0
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_confirmed_sector_and_current_geography_answers_use_graph_without_qdrant():
    graph = ProjectKnowledgeGraphBuilder().build(projection(
        sector="EnergyTech",
        location="Île-de-France, France",
        market="France",
        technology=None,
        data=None,
    ))

    class MustNotRetrieve:
        calls = 0

        async def retrieve(self, _question):
            self.calls += 1
            raise AssertionError("Current project-fact questions must not use regulatory retrieval")

    class MustNotGenerate:
        calls = 0

        async def generate(self, _request):
            self.calls += 1
            raise AssertionError("Current project-fact questions must not use an LLM")

    agent = RegulatoryAgent(retriever=MustNotRetrieve(), provider=MustNotGenerate())
    for question, expected in (
        ("Quel est le secteur de mon projet ?", "EnergyTech"),
        ("Quel est le secteur de ce projet ?", "EnergyTech"),
        ("Quel est le marché cible de mon projet ?", "France"),
        ("Dans quelle zone géographique mon projet opère-t-il actuellement ?", "Île-de-France, France"),
        ("Mon projet opère-t-il actuellement dans toute l’Union européenne ?", "Île-de-France, France"),
    ):
        context = GraphContextProvider().select(graph, question)
        result = await agent.run(AgentRequest(
            request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(), question=question,
            capability="regulatory", locale="fr", subject_type="project", subject_id=uuid.uuid4(),
            authorized_context=AuthorizedContext(
                subject_type="project", subject_id=uuid.uuid4(), graph_context=context,
            ),
        ))
        assert expected in (result.answer or "")
        assert result.structured_payload["answer_source"] == "PROJECT_GRAPH"


@pytest.mark.asyncio
async def test_graph_service_fails_closed_for_cross_user_and_revoked_membership():
    project_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()

    class Repository:
        async def has_active_membership(self, received_project_id, received_user_id):
            return received_project_id == project_id and received_user_id == owner_id

        async def load_knowledge_graph_projection(self, _project_id):
            return projection()

    service = ProjectKnowledgeGraphService(Repository())
    assert (await service.get_trusted_graph(project_id, owner_id)).nodes
    with pytest.raises(ProjectKnowledgeGraphAccessDenied):
        await service.get_trusted_graph(project_id, other_id)


def test_candidate_extractor_is_strict_local_and_pending_only():
    candidates = ProjectKnowledgeCandidateExtractor().extract(
        technology="forecasting engine, secure API",
        data_context="customer records; event logs",
    )

    assert [item.concept.canonical_label for item in candidates] == [
        "forecasting engine", "secure API", "customer records", "event logs",
    ]
    assert {item.concept.concept_type for item in candidates} == {"TECHNOLOGY", "DATA_CATEGORY"}
    assert all(item.as_project_fact_payload()["status"] == "pending_confirmation" for item in candidates)
    assert all(item.as_project_fact_payload()["provenance"]["extraction_method"] == "structured_delimited_v1" for item in candidates)
    assert ProjectKnowledgeCandidateExtractor().extract(
        technology="We may combine a service with predictive features.",
        data_context=None,
    ) == []


def test_atomic_concepts_normalize_conservatively_and_keep_source_provenance():
    assert normalize_concept_key("  Data-Platform ") == normalize_concept_key("data platform")
    graph = ProjectKnowledgeGraphBuilder().build(projection(
        technology=None,
        facts=(
            GraphFactProjection("technology", "Data Platform", "confirmed", "inferred", uuid.uuid4(), {"source_field": "technology"}),
            GraphFactProjection("technology", "data platform", "corrected", "inferred", uuid.uuid4(), {"source_field": "technology"}),
        ),
    ))
    concepts = [node for node in graph.nodes if node.type == KnowledgeNodeType.TECHNOLOGY]
    assert len(concepts) == 1
    assert concepts[0].provenance.source_type == "project_fact"
    assert concepts[0].provenance.source_field == "technology"
    assert concepts[0].properties["normalized_key"] == "data_platform"


def test_pending_confirmation_correction_and_rejection_evolve_only_trusted_graph():
    builder = ProjectKnowledgeGraphBuilder()
    candidate_id = uuid.uuid4()
    initial = builder.build(projection(technology="Long narrative technology profile that is not an atomic candidate.", facts=(
        GraphFactProjection("technology", "edge processing", "pending_confirmation", "inferred", candidate_id, {"source_field": "technology"}),
    )))
    confirmed = builder.build(projection(technology="Long narrative technology profile that is not an atomic candidate.", facts=(
        GraphFactProjection("technology", "edge processing", "confirmed", "inferred", candidate_id, {"source_field": "technology"}),
    )))
    corrected = builder.build(projection(technology="Long narrative technology profile that is not an atomic candidate.", facts=(
        GraphFactProjection("technology", "Edge Processing", "corrected", "inferred", candidate_id, {"source_field": "technology"}),
    )))
    rejected = builder.build(projection(technology=None, facts=(
        GraphFactProjection("technology", "Edge Processing", "deleted", "inferred", candidate_id, {"source_field": "technology"}),
    )))

    assert "edge processing" not in {node.label for node in initial.nodes}
    assert "edge processing" in {node.label for node in confirmed.nodes}
    assert "Edge Processing" in {node.label for node in corrected.nodes}
    assert "Edge Processing" not in {node.label for node in rejected.nodes}
    assert all(node.trust_status.value in {"CONFIRMED", "VERIFIED"} for node in confirmed.nodes)


def test_explicit_confirmed_lists_create_atomic_nodes_and_suppress_giant_canonical_node():
    long_profile = "operational component " * 90
    graph = ProjectKnowledgeGraphBuilder().build(projection(
        technology=long_profile,
        data="large narrative data profile " * 90,
        facts=(
            GraphFactProjection("technology", "service layer", "confirmed", "inferred", uuid.uuid4(), {"source_field": "technology"}),
            GraphFactProjection("technology", "storage adapter", "confirmed", "inferred", uuid.uuid4(), {"source_field": "technology"}),
            GraphFactProjection("data", "account records", "confirmed", "inferred", uuid.uuid4(), {"source_field": "data"}),
        ),
    ))
    labels = {node.label for node in graph.nodes}
    assert {"service layer", "storage adapter", "account records"} <= labels
    assert not any("operational component" in label or "large narrative" in label for label in labels)
    assert max(len(node.label) for node in graph.nodes) <= 120


def test_narrative_suppression_is_category_scoped_and_keeps_fallback_without_atomic_facts():
    technology_narrative = "Artificial intelligence and machine learning analyse customer energy data across the platform."
    data_narrative = "The project plans to collect and process detailed customer energy consumption records over time."
    builder = ProjectKnowledgeGraphBuilder()

    fallback = builder.build(projection(technology=technology_narrative, data=data_narrative))
    assert technology_narrative in {node.label for node in fallback.nodes}
    assert data_narrative in {node.label for node in fallback.nodes}
    assert all(node.properties.get("knowledge_kind") == "narrative_fallback" for node in fallback.nodes if node.label in {technology_narrative, data_narrative})

    suppressed = builder.build(projection(
        technology=technology_narrative,
        data=data_narrative,
        facts=(GraphFactProjection("technology", "Artificial Intelligence", "confirmed", "inferred", uuid.uuid4(), {"source_field": "technology"}),),
    ))
    labels = {node.label for node in suppressed.nodes}
    assert "Artificial Intelligence" in labels
    assert technology_narrative not in labels
    assert data_narrative in labels


def test_equivalent_canonical_and_confirmed_atomic_values_share_one_stable_node_with_fact_priority():
    fact_id = uuid.uuid4()
    graph = ProjectKnowledgeGraphBuilder().build(projection(
        technology="Artificial Intelligence",
        facts=(GraphFactProjection("technology", "artificial intelligence", "confirmed", "inferred", fact_id, {"source_field": "technology"}),),
    ))
    concepts = [node for node in graph.nodes if node.type == KnowledgeNodeType.TECHNOLOGY]
    assert len(concepts) == 1
    assert concepts[0].provenance.source_type == "project_fact"
    assert concepts[0].properties["normalized_key"] == "artificial_intelligence"
    edges = [edge for edge in graph.edges if edge.relation == KnowledgeRelation.USES_TECHNOLOGY]
    assert len(edges) == 1
    assert edges[0].provenance.source_type == "project_fact"


def test_source_field_semantics_drive_relations_without_cross_category_guessing():
    graph = ProjectKnowledgeGraphBuilder().build(projection(
        sector="EnergyTech / SaaS B2B",
        technology="PostgreSQL",
        data="Personal data",
        market="French SMEs",
        location="Paris, France",
        facts=(GraphFactProjection("provider", "OVHcloud", "confirmed", "inferred", uuid.uuid4(), {"source_field": "copilot_message"}),),
        business_model="B2B subscription",
    ))
    relation_by_label = {
        next(node.label for node in graph.nodes if node.id == edge.target): edge.relation
        for edge in graph.edges
        if edge.source.startswith("project:")
    }
    assert relation_by_label["EnergyTech / SaaS B2B"] == KnowledgeRelation.HAS_SECTOR
    assert relation_by_label["B2B subscription"] == KnowledgeRelation.HAS_BUSINESS_MODEL
    assert relation_by_label["French SMEs"] == KnowledgeRelation.TARGETS_MARKET
    assert relation_by_label["Paris, France"] == KnowledgeRelation.OPERATES_IN
    assert relation_by_label["PostgreSQL"] == KnowledgeRelation.USES_TECHNOLOGY
    assert relation_by_label["Personal data"] == KnowledgeRelation.PROCESSES_DATA
    assert relation_by_label["OVHcloud"] == KnowledgeRelation.USES_PROVIDER


def test_lifecycle_node_has_human_label_without_mutating_its_canonical_value():
    graph = ProjectKnowledgeGraphBuilder().build(projection())
    stage = next(node for node in graph.nodes if node.type == KnowledgeNodeType.LIFECYCLE_STAGE)
    assert stage.label == "Projet idée"
    assert stage.properties["canonical_value"] == "idea"


def test_verified_assessment_adds_only_persisted_metadata_and_evidence_provenance():
    assessment_id = uuid.uuid4()
    graph = ProjectKnowledgeGraphBuilder().build(projection(
        regulatory_assessment=GraphRegulatoryAssessmentProjection(
            id=assessment_id,
            version=2,
            verification_verdict="pass",
            domains=("Privacy",),
            evidence_organizations=("Example Authority",),
        ),
    ))
    types = {node.type for node in graph.nodes}
    assert {KnowledgeNodeType.REGULATORY_ASSESSMENT, KnowledgeNodeType.REGULATORY_DOMAIN, KnowledgeNodeType.EVIDENCE} <= types
    assert any(edge.relation == KnowledgeRelation.AFFECTED_BY and edge.trust_status.value == "VERIFIED" for edge in graph.edges)
    assert any(edge.relation == KnowledgeRelation.SUPPORTED_BY and edge.provenance.source_ref == str(assessment_id) for edge in graph.edges)
    without_assessment = ProjectKnowledgeGraphBuilder().build(projection(technology="Some technology"))
    assert KnowledgeNodeType.REGULATORY_DOMAIN not in {node.type for node in without_assessment.nodes}


def test_graph_context_selects_atomic_and_verified_second_hop_context_with_bounds():
    graph = ProjectKnowledgeGraphBuilder().build(projection(
        technology=None,
        data=None,
        facts=(
            GraphFactProjection("technology", "model pipeline", "confirmed", "inferred", uuid.uuid4(), {"source_field": "technology"}),
            GraphFactProjection("data", "customer records", "confirmed", "inferred", uuid.uuid4(), {"source_field": "data"}),
        ),
        regulatory_assessment=GraphRegulatoryAssessmentProjection(uuid.uuid4(), 1, "pass", ("Privacy",), ("Example Authority",)),
    ))
    privacy = GraphContextProvider().select(graph, "Quelles donnees personnelles mon projet traite-t-il ?")
    regulatory = GraphContextProvider().select(graph, "Quelle evaluation reglementaire est disponible ?")
    assert any(node.type == KnowledgeNodeType.DATA_CATEGORY for node in privacy.nodes)
    assert all(node.type in {KnowledgeNodeType.PROJECT, KnowledgeNodeType.DATA_CATEGORY} for node in privacy.nodes)
    assert {KnowledgeNodeType.REGULATORY_ASSESSMENT, KnowledgeNodeType.EVIDENCE} <= {node.type for node in regulatory.nodes}
    assert len(regulatory.nodes) <= GraphContextProvider.max_nodes
    assert len(regulatory.edges) <= GraphContextProvider.max_edges


def test_generic_non_ai_and_healthcare_topologies_are_not_forced_to_share_concepts():
    builder = ProjectKnowledgeGraphBuilder()
    healthcare = builder.build(projection(sector="Healthcare", technology="appointment portal", data="visit schedules", market="Clinics"))
    minimal = builder.build(projection(sector="Craft", technology=None, data=None, market="Local customers", location="Portugal"))
    healthcare_labels = {node.label for node in healthcare.nodes}
    minimal_labels = {node.label for node in minimal.nodes}
    assert "appointment portal" in healthcare_labels
    assert "appointment portal" not in minimal_labels
    assert not any("intelligence artificielle" in label.casefold() for label in minimal_labels)
    assert not any("personal data" in label.casefold() for label in minimal_labels)


def test_moderately_enriched_graph_and_context_are_bounded_and_fast():
    facts = tuple(
        GraphFactProjection("technology", f"component {index}", "confirmed", "inferred", uuid.uuid4(), {"source_field": "technology"})
        for index in range(50)
    )
    started = perf_counter()
    graph = ProjectKnowledgeGraphBuilder().build(projection(technology=None, facts=facts))
    build_duration = perf_counter() - started
    selected_started = perf_counter()
    context = GraphContextProvider().select(graph, "Quelle technologie utilise mon projet ?")
    selection_duration = perf_counter() - selected_started
    assert graph.metadata.node_count == 57  # project, stage, sector/data/market/location, document, and 50 concepts
    assert len(context.nodes) <= GraphContextProvider.max_nodes
    assert build_duration < 1
    assert selection_duration < 1
