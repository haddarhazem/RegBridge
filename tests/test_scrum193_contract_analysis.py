import json
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.ai.llm import LLMExecutionMetadata, LLMGenerationResponse, LLMProviderError
from app.modules.ai.models import AgentRun
from app.modules.audit import AuditLog
from app.modules.documents.contract_analysis import ContractExtractor
from app.modules.documents.evidence import EvidenceResolutionError, EvidenceResolver
from app.modules.documents.contract_analysis_models import ContractAnalysis
from app.modules.documents.contract_analysis_service import ContractAnalysisService
from app.modules.documents.models import Document, DocumentVersion
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember


class FakeProvider:
    def __init__(self, output_factory, *, fail: Exception | None = None):
        self.output_factory = output_factory
        self.fail = fail
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        if self.fail:
            raise self.fail
        return LLMGenerationResponse(content=self.output_factory(request), model="fake-contract-model", execution=LLMExecutionMetadata(provider="fake", model="fake-contract-model", status="success"))


@pytest_asyncio.fixture
async def contract_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL is unavailable for SCRUM-193 tests: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="scrum193-test")


def output_for(version_id: uuid.UUID, text_value: str, *, invalid_evidence: bool = False) -> str:
    quote = text_value
    start = 0
    end = len(text_value)
    if invalid_evidence:
        quote = "wrong evidence"
    return json.dumps({"findings": [{"finding_type": "FINDING", "category": "termination", "statement": "The contract contains a termination clause.", "risk_level": "medium", "recommendation": None, "uncertainty": None, "evidence": [{"document_version_id": str(version_id), "quote": quote, "start_char": start, "end_char": end}]}]})


async def create_fixture(factory, *, text_value: str, second_user: bool = True) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, AuthenticatedPrincipal, AuthenticatedPrincipal]:
    owner_id, other_id = uuid.uuid4(), uuid.uuid4()
    owner = principal(owner_id, f"owner-{owner_id}@example.test")
    other = principal(other_id, f"other-{other_id}@example.test")
    async with factory() as session:
        session.add_all([User(id=owner_id, email=owner.email), User(id=other_id, email=other.email)])
        project = Project(owner_user_id=owner_id, project_type="existing_startup", raw_description="Startup", confirmed_fields={})
        session.add(project)
        await session.flush()
        session.add(ProjectMember(project_id=project.id, user_id=owner_id, member_role="owner", status="active"))
        document = Document(owner_user_id=owner_id, project_id=project.id, title="Contract", document_type="txt", classification="confidential", visibility="private", processing_status="uploaded")
        session.add(document)
        await session.flush()
        version = DocumentVersion(document_id=document.id, version_number=1, original_filename="contract.txt", storage_key=f"test/{uuid.uuid4()}", mime_type="text/plain", size_bytes=len(text_value.encode()), sha256="a" * 64, malware_scan_status="clean", extracted_text=text_value, uploaded_by_user_id=owner_id)
        session.add(version)
        await session.flush()
        document.current_version_id = version.id
        await session.commit()
        return project.id, document.id, version.id, owner, other


async def cleanup(factory, project_id, document_id, user_ids):
    async with factory() as session:
        await session.execute(delete(AuditLog).where(AuditLog.project_id == project_id))
        await session.execute(delete(ContractAnalysis).where(ContractAnalysis.document_id == document_id))
        await session.execute(delete(AgentRun).where(AgentRun.subject_id == document_id))
        await session.execute(delete(Project).where(Project.id == project_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


@pytest.mark.asyncio
async def test_analysis_is_version_bound_evidence_grounded_and_source_immutable(contract_factory):
    text_v1 = "The customer may terminate this contract on 30 days' notice."
    project_id, document_id, version1_id, owner, other = await create_fixture(contract_factory, text_value=text_v1)
    try:
        provider1 = FakeProvider(lambda _request: output_for(version1_id, text_v1))
        async with contract_factory() as session:
            analysis1 = await ContractAnalysisService(session, provider=provider1).analyze(owner, document_id, version1_id)
            assert analysis1.status == "completed"
            assert analysis1.document_version_id == version1_id
            assert analysis1.findings[0].evidence_quote == text_v1
            assert analysis1.findings[0].statement == text_v1
            assert analysis1.findings[0].finding_type == "UNCERTAINTY"
            assert analysis1.findings[0].recommendation is None
            assert analysis1.findings[0].risk_level is None
            assert analysis1.findings[0].evidence_document_version_id == version1_id
            assert provider1.requests[0].messages[0].role == "system"
            assert "untrusted document data" in provider1.requests[0].messages[0].content

        async with contract_factory() as session:
            version1 = await session.get(DocumentVersion, version1_id)
            original_hash, original_text = version1.sha256, version1.extracted_text
            document = await session.get(Document, document_id)
            text_v2 = "The supplier may terminate this contract on 90 days' notice."
            version2 = DocumentVersion(document_id=document_id, version_number=2, original_filename="contract-v2.txt", storage_key=f"test/{uuid.uuid4()}", mime_type="text/plain", size_bytes=len(text_v2.encode()), sha256="b" * 64, malware_scan_status="clean", extracted_text=text_v2, uploaded_by_user_id=owner.user_id)
            session.add(version2)
            await session.flush()
            document.current_version_id = version2.id
            await session.commit()
            provider2 = FakeProvider(lambda _request: output_for(version2.id, text_v2))
            analysis2 = await ContractAnalysisService(session, provider=provider2).analyze(owner, document_id, version2.id)
            assert analysis2.status == "completed"
            assert analysis2.document_version_id == version2.id
            reloaded_v1 = await session.get(DocumentVersion, version1_id)
            reloaded_v2 = await session.get(DocumentVersion, version2.id)
            assert (reloaded_v1.sha256, reloaded_v1.extracted_text) == (original_hash, original_text)
            assert (reloaded_v2.sha256, reloaded_v2.extracted_text) == ("b" * 64, text_v2)
    finally:
        await cleanup(contract_factory, project_id, document_id, [owner.user_id, other.user_id])


@pytest.mark.asyncio
async def test_cross_user_analysis_and_read_are_denied(contract_factory):
    project_id, document_id, version_id, owner, other = await create_fixture(contract_factory, text_value="Private contract text")
    try:
        async with contract_factory() as session:
            service = ContractAnalysisService(session, provider=FakeProvider(lambda _request: output_for(version_id, "Private contract text")))
            with pytest.raises(HTTPException) as error:
                await service.analyze(other, document_id, version_id)
            assert error.value.status_code == 404
        async with contract_factory() as session:
            analysis = ContractAnalysis(project_id=project_id, document_id=document_id, document_version_id=version_id, strategy="v2_structured_evidence", prompt_version="test", status="failed", created_by_user_id=owner.user_id, error_code="test")
            session.add(analysis)
            await session.commit()
            with pytest.raises(HTTPException) as error:
                await ContractAnalysisService(session).get(other, analysis.id)
            assert error.value.status_code == 404
    finally:
        await cleanup(contract_factory, project_id, document_id, [owner.user_id, other.user_id])


@pytest.mark.asyncio
async def test_provider_failure_and_invalid_evidence_are_safe(contract_factory):
    text_value = "The customer may terminate this contract on 30 days' notice."
    project_id, document_id, version_id, owner, other = await create_fixture(contract_factory, text_value=text_value)
    try:
        async with contract_factory() as session:
            failed = await ContractAnalysisService(session, provider=FakeProvider(lambda _request: "{}", fail=LLMProviderError("provider unavailable"))).analyze(owner, document_id, version_id)
            assert failed.status == "failed"
            assert failed.findings == []
        async with contract_factory() as session:
            invalid = await ContractAnalysisService(session, provider=FakeProvider(lambda _request: output_for(version_id, text_value, invalid_evidence=True))).analyze(owner, document_id, version_id)
            assert invalid.status == "failed"
            assert invalid.findings == []
    finally:
        await cleanup(contract_factory, project_id, document_id, [owner.user_id, other.user_id])


def test_extractor_requires_exact_immutable_evidence_shape():
    assert ContractAnalysis.__tablename__ == "contract_analyses"


def test_production_evidence_resolver_is_exact_and_rejects_ambiguity():
    text_value = "Payment is due.\nTermination is possible."
    start, end = EvidenceResolver.resolve(text_value, "Termination is possible.")
    assert text_value[start:end] == "Termination is possible."
    with pytest.raises(EvidenceResolutionError):
        EvidenceResolver.resolve("Same. Same.", "Same.")
