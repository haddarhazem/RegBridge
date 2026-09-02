import uuid

import pytest

from app.modules.ai.context import (
    AuthorizedContextBuilder,
    ContextAuthorizationError,
    ProjectAuthorizationService,
    ProjectContextProjection,
    ProjectFactProjection,
)
from app.modules.ai.contracts import OrchestrationRequest
from app.modules.ai.projections import (
    AssessmentConclusionProjection,
    AssessmentProjection,
    ContractAnalysisProjection,
    ContractObservationProjection,
    DocumentProjection,
    RoadmapItemProjection,
    RoadmapProjection,
)
from app.modules.identity.schemas import AuthenticatedPrincipal


class ProjectionRepository:
    def __init__(self, user_id: uuid.UUID):
        self.user_id = user_id
        self.assessment_loads = 0
        self.roadmap_loads = 0
        self.assessment = AssessmentProjection(
            id=uuid.uuid4(), version=2, snapshot_id=uuid.uuid4(), status="completed",
            obligations=[AssessmentConclusionProjection(conclusion_id="o-1", category="obligation", statement="Obligation", source_refs=["point-1"])],
            recommendations=[AssessmentConclusionProjection(conclusion_id="r-1", category="recommendation", statement="Recommendation")],
            uncertainties=[AssessmentConclusionProjection(conclusion_id="u-1", category="uncertainty", statement="Uncertainty")],
            sources=["CNIL"],
        )
        self.roadmap = RoadmapProjection(
            id=uuid.uuid4(), version=3, status="active", regulatory_assessment_id=self.assessment.id,
            assessment_version=2,
            items=[RoadmapItemProjection(id=uuid.uuid4(), item_type="obligation", title="First", priority_order=1, status="in_progress", justification="Because")],
        )
        self.document_loads = 0
        self.analysis_loads = 0
        self.document = DocumentProjection(
            id=uuid.uuid4(), title="Contract", document_type="txt", classification="confidential", visibility="private",
            version_id=uuid.uuid4(), version_number=2, extracted_text="Authorized contract text",
        )
        self.analysis = ContractAnalysisProjection(
            id=uuid.uuid4(), document_id=self.document.id, document_version_id=self.document.version_id,
            strategy="v2_structured_evidence", status="completed",
            observations=[ContractObservationProjection(
                id=uuid.uuid4(), category="UNCERTAINTY", source_quote="Authorized passage",
                document_version_id=self.document.version_id, start_char=0, end_char=18,
            )],
        )

    async def has_active_membership(self, project_id, user_id):
        return user_id == self.user_id

    async def load_minimal_projection(self, project_id):
        return ProjectContextProjection(
            "idea", "FR", "goal",
            facts=(
                ProjectFactProjection("confirmed", "trusted", "inferred", "confirmed", {}, "low"),
            ),
        )

    async def load_latest_assessment_projection(self, project_id):
        self.assessment_loads += 1
        return self.assessment

    async def load_latest_roadmap_projection(self, project_id):
        self.roadmap_loads += 1
        return self.roadmap

    async def load_document_projection(self, project_id, user_id, document_id, version_id):
        self.document_loads += 1
        return self.document if document_id == self.document.id and version_id == self.document.version_id else None

    async def load_contract_analysis_projection(self, project_id, user_id, analysis_id, document_id, version_id):
        self.analysis_loads += 1
        return self.analysis if analysis_id == self.analysis.id and document_id == self.document.id and version_id == self.document.version_id else None


def request(user_id, question, *, document=None, analysis=None):
    return OrchestrationRequest(
        principal=AuthenticatedPrincipal(user_id=user_id, email="owner@example.test", roles=("entrepreneur",), provider="test"),
        subject_type="project", subject_id=uuid.uuid4(), question=question, intent_hint="regulatory", locale="fr",
        context_document_id=document.id if document else None,
        context_version_id=document.version_id if document else None,
        context_analysis_id=analysis.id if analysis else None,
    )


@pytest.mark.asyncio
async def test_context_loads_only_relevant_latest_projection_and_preserves_versions():
    user_id = uuid.uuid4()
    repository = ProjectionRepository(user_id)
    builder = AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository))

    general = await builder.build(request(user_id, "Quelles obligations concernent mon projet ?"), ["regulatory"])
    assert general.assessment is None and general.roadmap is None
    assert repository.assessment_loads == repository.roadmap_loads == 0
    assert [fact["value"] for fact in general.facts] == ["trusted"]

    assessment = await builder.build(request(user_id, "Pourquoi cette obligation s'applique-t-elle à mon projet ?"), ["regulatory"])
    assert assessment.assessment.version == 2
    assert assessment.assessment.snapshot_id == repository.assessment.snapshot_id
    assert assessment.assessment.obligations[0].source_refs == ["point-1"]
    assert assessment.roadmap is None
    assert repository.assessment_loads == 1 and repository.roadmap_loads == 0

    roadmap = await builder.build(request(user_id, "Quelles etapes sont encore a faire ?"), ["regulatory"])
    assert roadmap.roadmap.version == 3
    assert roadmap.roadmap.assessment_version == 2
    assert roadmap.roadmap.items[0].status == "in_progress"
    assert repository.assessment_loads == 1 and repository.roadmap_loads == 1


@pytest.mark.asyncio
async def test_context_authorization_denies_before_assessment_or_roadmap_load():
    repository = ProjectionRepository(uuid.uuid4())
    builder = AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository))
    denied_user = uuid.uuid4()

    with pytest.raises(ContextAuthorizationError):
        await builder.build(request(denied_user, "Pourquoi cette obligation s'applique-t-elle à mon projet ?"), ["regulatory"])
    assert repository.assessment_loads == 0
    assert repository.roadmap_loads == 0


@pytest.mark.asyncio
async def test_context_loads_exact_authorized_document_and_contract_analysis():
    user_id = uuid.uuid4()
    repository = ProjectionRepository(user_id)
    builder = AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository))

    context = await builder.build(
        request(user_id, "Explique ce contrat", document=repository.document, analysis=repository.analysis),
        ["regulatory"],
    )

    assert context.document.version_id == repository.document.version_id
    assert context.document.extracted_text == "Authorized contract text"
    assert context.contract_analysis.id == repository.analysis.id
    assert context.contract_analysis.observations[0].source_quote == "Authorized passage"
    assert repository.document_loads == repository.analysis_loads == 1


@pytest.mark.asyncio
async def test_document_context_requires_exact_pair_and_rejects_missing_projection():
    user_id = uuid.uuid4()
    repository = ProjectionRepository(user_id)
    builder = AuthorizedContextBuilder(repository, ProjectAuthorizationService(repository))

    with pytest.raises(ValueError):
        OrchestrationRequest(
            principal=AuthenticatedPrincipal(user_id=user_id, email="owner@example.test", roles=("entrepreneur",), provider="test"),
            subject_type="project", subject_id=uuid.uuid4(), intent_hint="regulatory",
            context_document_id=repository.document.id,
        )

    with pytest.raises(ContextAuthorizationError):
        await builder.build(
            request(user_id, "Explique ce contrat", document=DocumentProjection(
                id=uuid.uuid4(), title="Other", document_type="txt", classification="confidential", visibility="private",
                version_id=uuid.uuid4(), version_number=1,
            )),
            ["regulatory"],
        )
