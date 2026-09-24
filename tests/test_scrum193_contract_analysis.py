"""PostgreSQL-backed evidence and authorization coverage for contract analysis."""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.ai.models import AgentRun
from app.modules.audit import AuditLog
from app.modules.documents.contract_analysis import ContractAnalyzer, ContractExtractionError
from app.modules.documents.contract_analysis_models import ContractAnalysis
from app.modules.documents.contract_analysis_service import ContractAnalysisService
from app.modules.documents.contract_semantic import SemanticClauseDraft, SemanticContractResult, SemanticEvidenceClaim
from app.modules.documents.router import analysis_response
from app.modules.documents.models import Document, DocumentVersion
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember


SYNTHETIC_CONTRACT = """PARTIES
Entre EnerSight SAS, ci-après le Prestataire, et Client SA, ci-après le Client.

OBJET
Le Prestataire fournit une plateforme SaaS de suivi énergétique.

PERIMETRE
La prestation couvre l'acces a la plateforme et son support standard.

PAIEMENT
Le Client règle les factures selon les modalités convenues entre les parties.

DURÉE
Le contrat est conclu pour 12 mois. Il prend automatiquement fin après 24 mois.

CONFIDENTIALITÉ
Le Client garde confidentielles les informations du Prestataire.

PROPRIÉTÉ INTELLECTUELLE
La propriété intellectuelle des livrables sera définie ultérieurement.

RESPONSABILITÉ
La responsabilité du Prestataire est illimitée.

DONNÉES PERSONNELLES
Les parties traitent des données personnelles des utilisateurs.

DROIT APPLICABLE
Le présent contrat est soumis au droit français."""


@pytest_asyncio.fixture
async def contract_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable for contract tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="contract-test")


async def create_fixture(factory, *, text_value: str = SYNTHETIC_CONTRACT):
    owner_id, other_id = uuid.uuid4(), uuid.uuid4()
    owner, other = principal(owner_id, f"owner-{owner_id}@example.test"), principal(other_id, f"other-{other_id}@example.test")
    async with factory() as session:
        session.add_all([User(id=owner_id, email=owner.email), User(id=other_id, email=other.email)])
        project = Project(owner_user_id=owner_id, project_type="existing_startup", raw_description="Synthetic contract project", confirmed_fields={})
        session.add(project)
        await session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=owner_id, member_role="owner", status="active"))
        document = Document(owner_user_id=owner_id, project_id=project.id, title="Synthetic contract", document_type="txt", classification="confidential", visibility="private", processing_status="uploaded")
        session.add(document)
        await session.flush()
        version = DocumentVersion(document_id=document.id, version_number=1, original_filename="synthetic-contract.txt", storage_key=f"test/{uuid.uuid4()}", mime_type="text/plain", size_bytes=len(text_value.encode()), sha256="a" * 64, malware_scan_status="clean", extracted_text=text_value, uploaded_by_user_id=owner_id)
        session.add(version)
        await session.flush()
        document.current_version_id = version.id
        await session.commit()
        return project.id, document.id, version.id, owner, other


async def cleanup(factory, project_id, document_id, user_ids):
    async with factory() as session:
        await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
        await session.execute(delete(ContractAnalysis).where(ContractAnalysis.project_id == project_id))
        await session.execute(delete(AgentRun).where(AgentRun.subject_id == document_id))
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


def clause_by_type(output, clause_type):
    return next(item for item in output.clauses if item.clause_type == clause_type)


def test_semantic_provider_disabled_returns_only_verified_document_structure():
    version_id = uuid.uuid4()
    output = ContractAnalyzer().analyze(text=SYNTHETIC_CONTRACT, document_version_id=version_id)

    assert output.semantic_status == "partial"
    assert output.clauses
    assert {item.clause_type for item in output.clauses} == {"other"}
    assert all(item.verification_status == "VERIFIED" for item in output.clauses)
    assert all(item.source_text in SYNTHETIC_CONTRACT for item in output.clauses)


class _SemanticFixture:
    async def analyze(self, *, sections, parties):
        payment_section = next(section for section in sections if section.heading == "PAIEMENT")
        liability_section = next(section for section in sections if "RESPONS" in (section.heading or ""))
        return SemanticContractResult(
            contract_type="Contrat de prestation de services",
            clauses=[
                SemanticClauseDraft(section_id=payment_section.section_id, clause_type="payment", status="AMBIGUOUS", risk_level="medium", summary="Echeance ambigue.", issues=["Echeance non precisee."], evidence_claims=[SemanticEvidenceClaim(section_id=payment_section.section_id, quote=payment_section.raw_text)]),
                SemanticClauseDraft(section_id=liability_section.section_id, clause_type="liability", status="AMBIGUOUS", risk_level="high", summary="Responsabilite sans plafond.", issues=["Aucun plafond identifie."], evidence_claims=[SemanticEvidenceClaim(section_id=liability_section.section_id, quote=liability_section.raw_text)]),
            ],
        )


def test_empty_contract_is_rejected_and_absent_non_compete_is_not_created():
    with pytest.raises(ContractExtractionError):
        ContractAnalyzer().analyze(text="", document_version_id=uuid.uuid4())
    output = ContractAnalyzer().analyze(text=SYNTHETIC_CONTRACT, document_version_id=uuid.uuid4())
    assert "non_compete" not in {item.clause_type for item in output.clauses}


def test_generic_descriptive_words_do_not_fabricate_scope_or_deliverables_clauses():
    output = ContractAnalyzer().analyze(
        text="Le prestataire fournit des services et des livrables pour le client.",
        document_version_id=uuid.uuid4(),
    )
    detected = {item.clause_type for item in output.clauses}
    assert "scope" not in detected
    assert "deliverables" not in detected


@pytest.mark.asyncio
async def test_analysis_is_version_bound_persisted_and_source_immutable(contract_factory):
    project_id, document_id, version_id, owner, other = await create_fixture(contract_factory)
    try:
        async with contract_factory() as session:
            before = await session.get(DocumentVersion, version_id)
            original = (before.sha256, before.extracted_text)
            analysis = await ContractAnalysisService(session, semantic_analyzer=_SemanticFixture()).analyze(owner, document_id, version_id)
            assert analysis.verification_status == "completed"
            assert analysis.document_version_id == version_id
            assert analysis.analysis_version == 1
            response = analysis_response(analysis)
            assert response.document_id == document_id
            assert response.parties
            assert any(item.clause_type == "payment" and item.status == "AMBIGUOUS" for item in response.clauses)
            assert response.risk_index.score == min(
                100,
                2 * (
                    response.risk_index.severity_points
                    + (2 * response.risk_index.missing_clause_count)
                    + (2 * response.risk_index.contradiction_count)
                ),
            )
            assert response.risk_index.contributors
            assert any(item.clause_type == "liability" and item.risk_level == "high" for item in analysis.clauses)
            liability = next(item for item in analysis.clauses if item.clause_type == "liability")
            assert liability.source_refs["evidence"][0]["quote"] == liability.extracted_text
            run = await session.get(AgentRun, analysis.agent_run_id)
            assert run is not None
            trace_json = json.dumps({"request": run.request_payload, "response": run.response_payload})
            assert SYNTHETIC_CONTRACT not in trace_json
            assert "responsabilitÃ© du Prestataire" not in trace_json
            after = await session.get(DocumentVersion, version_id)
            assert (after.sha256, after.extracted_text) == original
    finally:
        await cleanup(contract_factory, project_id, document_id, [owner.user_id, other.user_id])


@pytest.mark.asyncio
async def test_cross_project_analysis_and_read_are_denied(contract_factory):
    project_id, document_id, version_id, owner, other = await create_fixture(contract_factory)
    try:
        async with contract_factory() as session:
            service = ContractAnalysisService(session)
            with pytest.raises(HTTPException) as error:
                await service.analyze(other, document_id, version_id)
            assert error.value.status_code == 404
            analysis = await service.analyze(owner, document_id, version_id)
        async with contract_factory() as session:
            with pytest.raises(HTTPException) as error:
                await ContractAnalysisService(session).get(other, analysis.id)
            assert error.value.status_code == 404
    finally:
        await cleanup(contract_factory, project_id, document_id, [owner.user_id, other.user_id])
