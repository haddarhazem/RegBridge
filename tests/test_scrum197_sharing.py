import uuid
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import get_settings
from app.modules.audit import AuditLog
from app.modules.compliance.models import ComplianceScoreCalculation
from app.modules.documents.models import Document, DocumentVersion
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember
from app.modules.projects.profile_models import StartupProfile, StartupProfileField, StartupProfileRevision
from app.modules.sharing.models import InvestorShareGrant
from app.modules.sharing.schemas import RevokeShareRequest, ShareGrantCreate
from app.modules.sharing.service import SharingService

@pytest_asyncio.fixture
async def sharing_factory():
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection: await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose(); pytest.skip(f"PostgreSQL unavailable for SCRUM-197: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try: yield factory
    finally: await engine.dispose()

def principal(user_id: uuid.UUID, email: str) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(user_id=user_id, email=email, roles=(), provider="scrum197-test")

async def fixture(factory):
    owner_id, u2_id, u3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    owner, u2, u3 = (principal(i, f"{label}-{i}@example.test") for i, label in ((owner_id,"owner"),(u2_id,"u2"),(u3_id,"u3")))
    async with factory() as session:
        session.add_all([User(id=owner_id,email=owner.email),User(id=u2_id,email=u2.email),User(id=u3_id,email=u3.email)])
        project = Project(owner_user_id=owner_id, project_type="existing_startup", raw_description="sharing", confirmed_fields={}); other = Project(owner_user_id=u3_id, project_type="existing_startup", raw_description="other", confirmed_fields={})
        session.add_all([project, other]); await session.flush()
        session.add(ProjectMember(project_id=project.id,user_id=owner_id,member_role="owner",status="active")); await session.flush()
        profile=StartupProfile(project_id=project.id,current_revision=1); session.add(profile); await session.flush()
        revision=StartupProfileRevision(profile_id=profile.id,revision_number=1,snapshot=[{"field_name":"investor_summary","visibility":"INVESTOR_SHARED","value":"safe"},{"field_name":"internal_notes","visibility":"PRIVATE","value":"secret"}],changed_by_user_id=owner_id); session.add(revision)
        document=Document(owner_user_id=owner_id,project_id=project.id,title="pitch",document_type="pdf",classification="confidential",visibility="private",processing_status="uploaded"); session.add(document); await session.flush()
        version1=DocumentVersion(document_id=document.id,version_number=1,original_filename="pitch-v1.pdf",storage_key=f"share/{uuid.uuid4()}",mime_type="application/pdf",size_bytes=10,sha256="a"*64,malware_scan_status="clean",uploaded_by_user_id=owner_id); session.add(version1); await session.flush(); document.current_version_id=version1.id
        version2=DocumentVersion(document_id=document.id,version_number=2,original_filename="pitch-v2.pdf",storage_key=f"share/{uuid.uuid4()}",mime_type="application/pdf",size_bytes=11,sha256="b"*64,malware_scan_status="clean",uploaded_by_user_id=owner_id); session.add(version2)
        score=ComplianceScoreCalculation(project_id=project.id,method_key="compliance-maturity-unweighted",method_version="v1",evidence_policy_version="active-evidence-required-v1",rounding_policy="Decimal-half-up-2dp",numerator=1,denominator=2,score=50,evidence_coverage=50,input_snapshot={"controls":[]},explanation={"limitations":["maturity indicator, not certification"],"evidence_used":[{"evidence_ids":["private-evidence"]}]}); session.add(score); await session.commit()
        return {"project":project.id,"other":other.id,"owner":owner,"u2":u2,"u3":u3,"revision":revision.id,"v1":version1.id,"v2":version2.id,"document":document.id,"score":score.id}

async def cleanup(factory, data):
    async with factory() as session:
        await session.execute(delete(AuditLog).where(AuditLog.project_id.in_([data["project"],data["other"]])))
        await session.execute(delete(InvestorShareGrant).where(InvestorShareGrant.project_id == data["project"]))
        await session.execute(delete(ComplianceScoreCalculation).where(ComplianceScoreCalculation.project_id == data["project"]))
        await session.execute(delete(StartupProfileRevision).where(StartupProfileRevision.id == data["revision"]))
        await session.execute(delete(StartupProfileField).where(StartupProfileField.profile_id.in_(select(StartupProfile.id).where(StartupProfile.project_id == data["project"]))))
        await session.execute(delete(StartupProfile).where(StartupProfile.project_id == data["project"]))
        await session.execute(delete(DocumentVersion).where(DocumentVersion.document_id.in_(select(Document.id).where(Document.project_id == data["project"]))))
        await session.execute(delete(Document).where(Document.project_id == data["project"]))
        await session.execute(delete(ProjectMember).where(ProjectMember.project_id.in_([data["project"],data["other"]])))
        await session.execute(delete(Project).where(Project.id.in_([data["project"],data["other"]])))
        await session.execute(delete(User).where(User.id.in_([data["owner"].user_id,data["u2"].user_id,data["u3"].user_id]))); await session.commit()

@pytest.mark.asyncio
async def test_resource_level_sharing_and_recipient_isolation(sharing_factory):
    data=await fixture(sharing_factory)
    try:
        async with sharing_factory() as session:
            service=SharingService(session); profile=await service.create(data["owner"],data["project"],ShareGrantCreate(recipient_user_id=data["u2"].user_id,resource_type="STARTUP_PROFILE_REVISION",resource_id=data["revision"]))
            score=await service.create(data["owner"],data["project"],ShareGrantCreate(recipient_user_id=data["u3"].user_id,resource_type="COMPLIANCE_SCORE_CALCULATION",resource_id=data["score"]))
            same=await service.create(data["owner"],data["project"],ShareGrantCreate(recipient_user_id=data["u2"].user_id,resource_type="STARTUP_PROFILE_REVISION",resource_id=data["revision"]))
            assert same.id == profile.id and score.recipient_user_id == data["u3"].user_id
        async with sharing_factory() as session:
            _, payload=await SharingService(session).access(data["u2"],profile.id); assert payload["fields"] == [{"field_name":"investor_summary","visibility":"INVESTOR_SHARED","value":"safe"}]
            with pytest.raises(HTTPException): await SharingService(session).access(data["u3"],profile.id)
            with pytest.raises(HTTPException): await SharingService(session).access(data["u2"],score.id)
    finally: await cleanup(sharing_factory,data)

@pytest.mark.asyncio
async def test_exact_document_version_revocation_and_audit(sharing_factory):
    data=await fixture(sharing_factory)
    try:
        async with sharing_factory() as session:
            service=SharingService(session); grant=await service.create(data["owner"],data["project"],ShareGrantCreate(recipient_user_id=data["u2"].user_id,resource_type="DOCUMENT_VERSION",resource_id=data["document"],resource_version_id=data["v1"]))
        async with sharing_factory() as session:
            _,payload=await SharingService(session).access(data["u2"],grant.id); assert payload["document_version_id"] == data["v1"] and "storage_key" not in payload and "extracted_text" not in payload
            revoked=await SharingService(session).revoke(data["owner"],data["project"],grant.id,RevokeShareRequest(reason="done")); assert revoked.status == "REVOKED"
            with pytest.raises(HTTPException): await SharingService(session).access(data["u2"],grant.id)
            actions=list((await session.scalars(select(AuditLog.action).where(AuditLog.project_id == data["project"]))).all()); assert "GRANT_CREATED" in actions and "SHARED_RESOURCE_ACCESSED" in actions and "GRANT_REVOKED" in actions
    finally: await cleanup(sharing_factory,data)

@pytest.mark.asyncio
async def test_score_safe_metadata_no_transitive_evidence_and_authority(sharing_factory):
    data=await fixture(sharing_factory)
    try:
        async with sharing_factory() as session:
            service=SharingService(session)
            with pytest.raises(HTTPException): await service.create(data["u2"],data["project"],ShareGrantCreate(recipient_user_id=data["u3"].user_id,resource_type="COMPLIANCE_SCORE_CALCULATION",resource_id=data["score"]))
            grant=await service.create(data["owner"],data["project"],ShareGrantCreate(recipient_user_id=data["u2"].user_id,resource_type="COMPLIANCE_SCORE_CALCULATION",resource_id=data["score"]))
        async with sharing_factory() as session:
            _,payload=await SharingService(session).access(data["u2"],grant.id); assert payload["score"] == 50.0 and payload["method_version"] == "v1" and "private-evidence" not in str(payload)
            with pytest.raises(HTTPException): await SharingService(session).access(data["u3"],grant.id)
            with pytest.raises(HTTPException): await SharingService(session).create(data["owner"],data["other"],ShareGrantCreate(recipient_user_id=data["u2"].user_id,resource_type="COMPLIANCE_SCORE_CALCULATION",resource_id=data["score"]))
    finally: await cleanup(sharing_factory,data)

@pytest.mark.asyncio
async def test_invalid_types_idor_and_repeated_revocation_fail_closed(sharing_factory):
    data=await fixture(sharing_factory)
    try:
        async with sharing_factory() as session:
            service=SharingService(session)
            with pytest.raises(HTTPException): await service.create(data["owner"],data["project"],ShareGrantCreate(recipient_user_id=data["u2"].user_id,resource_type="DOCUMENT_VERSION",resource_id=data["document"]))
            with pytest.raises(HTTPException): await service.create(data["owner"],data["project"],ShareGrantCreate(recipient_user_id=data["u2"].user_id,resource_type="STARTUP_PROFILE_REVISION",resource_id=data["score"]))
            grant=await service.create(data["owner"],data["project"],ShareGrantCreate(recipient_user_id=data["u2"].user_id,resource_type="STARTUP_PROFILE_REVISION",resource_id=data["revision"]))
            with pytest.raises(HTTPException): await service.revoke(data["owner"],data["other"],grant.id,RevokeShareRequest())
            assert (await service.revoke(data["owner"],data["project"],grant.id,RevokeShareRequest())).status == "REVOKED"
            assert (await service.revoke(data["owner"],data["project"],grant.id,RevokeShareRequest())).status == "REVOKED"
    finally: await cleanup(sharing_factory,data)
