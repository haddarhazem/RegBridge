import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.audit import AuditLog
from app.modules.compliance.models import ComplianceControlDefinition, ComplianceEvidence, ComplianceFramework, ComplianceFrameworkVersion, ComplianceScoreCalculation, ControlEvidenceLink, ProjectComplianceControl, ProjectFrameworkAdoption
from app.modules.compliance.schemas import AdoptionCreate, ControlStatePatch, EvidenceCreate, EvidenceRevoke
from app.modules.compliance.service import ComplianceService
from app.modules.compliance.score_service import ComplianceScoreService
from app.modules.documents.models import Document, DocumentVersion
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.identity.models import User
from app.modules.projects.models import Project, ProjectMember


@pytest_asyncio.fixture
async def compliance_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable for SCRUM-194: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="scrum194-test")


async def create_fixture(factory):
    owner_id, other_id = uuid.uuid4(), uuid.uuid4()
    owner = principal(owner_id, f"owner-{owner_id}@example.test")
    other = principal(other_id, f"other-{other_id}@example.test")
    framework = ComplianceFramework(stable_key=f"TEST-{uuid.uuid4()}", name="Synthetic Test Framework")
    async with factory() as session:
        session.add_all([User(id=owner_id, email=owner.email), User(id=other_id, email=other.email)])
        project = Project(owner_user_id=owner_id, project_type="existing_startup", raw_description="Compliance test", confirmed_fields={})
        other_project = Project(owner_user_id=other_id, project_type="existing_startup", raw_description="Other project", confirmed_fields={})
        session.add_all([project, other_project])
        await session.flush()
        session.add_all([
            ProjectMember(project_id=project.id, user_id=owner_id, member_role="owner", status="active"),
            ProjectMember(project_id=other_project.id, user_id=other_id, member_role="owner", status="active"),
            framework,
        ])
        await session.flush()
        version1 = ComplianceFrameworkVersion(framework_id=framework.id, version_identifier="V1", status="active")
        version2 = ComplianceFrameworkVersion(framework_id=framework.id, version_identifier="V2", status="active")
        session.add_all([version1, version2])
        await session.flush()
        definition1 = ComplianceControlDefinition(framework_version_id=version1.id, stable_key="SYN-001", title="Synthetic control", source_references=[{"source_id": "synthetic-source-1"}])
        definition2 = ComplianceControlDefinition(framework_version_id=version2.id, stable_key="SYN-001", title="Synthetic control V2", source_references=[{"source_id": "synthetic-source-2"}])
        session.add_all([definition1, definition2])
        document = Document(owner_user_id=owner_id, project_id=project.id, title="Evidence", document_type="txt", classification="confidential", visibility="private", processing_status="uploaded")
        session.add(document)
        await session.flush()
        document_version = DocumentVersion(document_id=document.id, version_number=1, original_filename="evidence.txt", storage_key=f"test/{uuid.uuid4()}", mime_type="text/plain", size_bytes=20, sha256="c" * 64, malware_scan_status="clean", extracted_text="Synthetic evidence", uploaded_by_user_id=owner_id)
        session.add(document_version)
        await session.flush()
        document.current_version_id = document_version.id
        await session.commit()
        return project.id, other_project.id, document_version.id, owner, other, framework.id, version1.id, version2.id


async def cleanup(factory, ids):
    project_id, other_project_id, document_version_id, owner, other, framework_id, version1_id, version2_id = ids
    async with factory() as session:
        await session.execute(delete(AuditLog).where(AuditLog.project_id.in_([project_id, other_project_id])))
        await session.execute(delete(ControlEvidenceLink).where(ControlEvidenceLink.project_control_id.in_(select(ProjectComplianceControl.id).where(ProjectComplianceControl.project_id.in_([project_id, other_project_id])))))
        await session.execute(delete(ComplianceEvidence).where(ComplianceEvidence.project_id.in_([project_id, other_project_id])))
        await session.execute(delete(ProjectComplianceControl).where(ProjectComplianceControl.project_id.in_([project_id, other_project_id])))
        await session.execute(delete(ComplianceScoreCalculation).where(ComplianceScoreCalculation.project_id.in_([project_id, other_project_id])))
        await session.execute(delete(ProjectFrameworkAdoption).where(ProjectFrameworkAdoption.project_id.in_([project_id, other_project_id])))
        await session.execute(delete(ComplianceControlDefinition).where(ComplianceControlDefinition.framework_version_id.in_([version1_id, version2_id])))
        await session.execute(delete(ComplianceFrameworkVersion).where(ComplianceFrameworkVersion.id.in_([version1_id, version2_id])))
        await session.execute(delete(ComplianceFramework).where(ComplianceFramework.id == framework_id))
        await session.execute(delete(DocumentVersion).where(DocumentVersion.id == document_version_id))
        await session.execute(delete(Document).where(Document.project_id == project_id))
        await session.execute(delete(Project).where(Project.id.in_([project_id, other_project_id])))
        await session.execute(delete(User).where(User.id.in_([owner.user_id, other.user_id])))
        await session.commit()


@pytest.mark.asyncio
async def test_materialized_controls_versions_evidence_history_and_revocation(compliance_factory):
    ids = await create_fixture(compliance_factory)
    project_id, other_project_id, document_version_id, owner, other, framework_id, version1_id, version2_id = ids
    try:
        async with compliance_factory() as session:
            service = ComplianceService(session)
            adoption1 = await service.adopt(owner, project_id, AdoptionCreate(framework_version_id=version1_id))
            assert (await service.adopt(owner, project_id, AdoptionCreate(framework_version_id=version1_id))).id == adoption1.id
            controls1 = await service.controls(owner, project_id)
            assert adoption1.status == "active"
            assert len(controls1) == 1 and controls1[0].framework_version_id == version1_id
            assert controls1[0].definition.source_references == [{"source_id": "synthetic-source-1"}]
            evidence_document = await service.attach_evidence(owner, project_id, EvidenceCreate(control_id=controls1[0].id, document_version_id=document_version_id))
            evidence_declaration = await service.attach_evidence(owner, project_id, EvidenceCreate(control_id=controls1[0].id, declaration_type="policy_ack", declaration_value="declared"))
            assert evidence_document.status == evidence_declaration.status == "ACTIVE"
            await service.revoke_evidence(owner, project_id, evidence_document.id, EvidenceRevoke(reason="withdrawn"))
            await service.revoke_evidence(owner, project_id, evidence_document.id, EvidenceRevoke(reason="withdrawn again"))
        async with compliance_factory() as session:
            evidence = list((await session.scalars(select(ComplianceEvidence).where(ComplianceEvidence.project_id == project_id).order_by(ComplianceEvidence.created_at))).all())
            assert [item.status for item in evidence] == ["REVOKED", "ACTIVE"]
            adoption2 = await ComplianceService(session).adopt(owner, project_id, AdoptionCreate(framework_version_id=version2_id))
            controls = await ComplianceService(session).controls(owner, project_id)
            assert adoption2.framework_version_id == version2_id
            assert {control.framework_version_id for control in controls} == {version1_id, version2_id}
            adoptions = list((await session.scalars(select(ProjectFrameworkAdoption).where(ProjectFrameworkAdoption.project_id == project_id).order_by(ProjectFrameworkAdoption.adopted_at))).all())
            assert [item.status for item in adoptions] == ["superseded", "active"]
            history = await ComplianceService(session).evidence_for_control(owner, project_id, controls[0].id)
            assert history[0].status == "REVOKED"
    finally:
        await cleanup(compliance_factory, ids)


@pytest.mark.asyncio
async def test_cross_user_and_cross_project_evidence_are_denied(compliance_factory):
    ids = await create_fixture(compliance_factory)
    project_id, other_project_id, document_version_id, owner, other, framework_id, version1_id, version2_id = ids
    try:
        async with compliance_factory() as session:
            service = ComplianceService(session)
            adoption = await service.adopt(owner, project_id, AdoptionCreate(framework_version_id=version1_id))
            control = (await service.controls(owner, project_id))[0]
            with pytest.raises(HTTPException):
                await service.controls(other, project_id)
            with pytest.raises(HTTPException):
                await service.attach_evidence(other, project_id, EvidenceCreate(control_id=control.id, declaration_type="ack", declaration_value="no"))
            with pytest.raises(HTTPException):
                await service.attach_evidence(owner, other_project_id, EvidenceCreate(control_id=control.id, document_version_id=document_version_id))
    finally:
        await cleanup(compliance_factory, ids)


@pytest.mark.asyncio
async def test_postgresql_score_snapshot_history_and_authorization(compliance_factory):
    ids = await create_fixture(compliance_factory)
    project_id, _, document_version_id, owner, other, _, version1_id, _ = ids
    try:
        async with compliance_factory() as session:
            service = ComplianceService(session)
            await service.adopt(owner, project_id, AdoptionCreate(framework_version_id=version1_id))
            control = (await service.controls(owner, project_id))[0]
            await service.update_control(owner, project_id, control.id, ControlStatePatch(status="SATISFIED"))
            evidence = await service.attach_evidence(owner, project_id, EvidenceCreate(control_id=control.id, document_version_id=document_version_id))
            first = await ComplianceScoreService(session).calculate_current(owner, project_id, version1_id)
            await session.commit()
            assert first.score == 100 and first.input_snapshot["controls"][0]["status"] == "SATISFIED"
        async with compliance_factory() as session:
            score_service = ComplianceScoreService(session)
            old = await score_service.latest(owner, project_id, version1_id)
            await ComplianceService(session).revoke_evidence(owner, project_id, evidence.id, EvidenceRevoke(reason="withdrawn"))
            newer = await score_service.calculate_current(owner, project_id, version1_id)
            await session.commit()
            assert old.score == 100 and newer.score == 0 and old.explanation["evidence_used"]
            with pytest.raises(HTTPException): await score_service.calculate_current(other, project_id, version1_id)
            with pytest.raises(HTTPException): await score_service.history(other, project_id, version1_id)
    finally:
        await cleanup(compliance_factory, ids)
