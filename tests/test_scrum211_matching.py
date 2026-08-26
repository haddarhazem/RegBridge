import uuid
import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, text, select, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import get_settings
from app.main import app
from app.db.session import get_session
from app.modules.audit import AuditLog
from app.modules.identity.dependencies import get_authenticated_principal
from app.modules.identity.models import User
from app.modules.identity.schemas import AuthenticatedPrincipal
from app.modules.projects.models import Project, ProjectMember, StartupResearchNeed, StartupResearchNeedVersion, ResearchMatchRun, ResearchMatchResult
from app.modules.documents.models import Document, DocumentVersion
from app.modules.research.models import (ResearcherProfile, ResearchOutput, ResearchOutputVersion,
    ResearchExtractionRun, ResearchDiscovery, ResearchDiscoveryVersion)
from app.modules.research.discovery import DiscoveryService
from app.modules.projects.matching_service import ResearchMatchingService, _evidence, _uncertainties
from app.modules.projects.schemas import IdeaProjectCreate, ResearchNeedPayload
from app.modules.projects.service import ProjectService

@pytest_asyncio.fixture
async def factory():
    engine=create_async_engine(get_settings().database_url,pool_pre_ping=True)
    try:
        async with engine.connect() as c: await c.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        await engine.dispose(); pytest.skip(f"PostgreSQL unavailable: {exc}")
    f=async_sessionmaker(engine,expire_on_commit=False)
    try: yield f
    finally: await engine.dispose()

def actor(uid,email): return AuthenticatedPrincipal(user_id=uid,email=email,roles=(),provider="scrum211-test")

def test_evidence_gate_rejects_generic_and_wrong_problem():
    n={"domains":["manufacturing"],"technologies":["computer vision"],"research_problem":"surface defect inspection","keywords":["defect"]}
    assert _evidence(n,{"domains":["manufacturing"],"technologies":["computer vision"],"research_problem":"surface defect inspection"})[0]
    assert not _evidence(n,{"domains":["marine"],"technologies":["computer vision"],"research_problem":"species classification"})[0]

def test_scrum211_unknown_field_is_uncertainty_not_mismatch():
    need = {"domains": ["industrial manufacturing"], "technologies": [], "research_problem": "surface defect inspection", "keywords": ["inspection"]}
    item = {"domains": ["industrial manufacturing"], "technologies": ["computer vision"], "research_problem": ["surface defect inspection"], "keywords": ["inspection"]}
    eligible, reasons, _, _ = _evidence(need, item)
    assert eligible and "PROBLEM_LEXICAL_ALIGNMENT" in reasons
    assert "TECHNOLOGY_LEXICAL_ALIGNMENT" not in reasons
    assert _uncertainties(need, item) == ["MISSING_STARTUP_TECHNOLOGY"]

@pytest.mark.asyncio
async def test_scrum211_postgres_version_run_round_trip(factory):
    uid=uuid.uuid4(); email=f"scrum211-{uid}@example.test"; pid=None
    async with factory() as s: s.add(User(id=uid,email=email)); await s.commit()
    try:
        async with factory() as s:
            a=actor(uid,email); pid=(await ProjectService(s).create_idea(a,IdeaProjectCreate(display_name="Matching"))).id; n,v1=await ResearchMatchingService(s).create_need(a,pid,ResearchNeedPayload(domains=["manufacturing"],technologies=["computer vision"],research_problem="surface defects",keywords=["inspection"])); _,v2=await ResearchMatchingService(s).version_need(a,pid,n.id,ResearchNeedPayload(domains=["energy"],technologies=[],research_problem="demand forecasting",keywords=[])); run=await ResearchMatchingService(s).run(a,pid,n.id,v1.id); assert v1.version_number==1 and v2.version_number==2 and run.need_version_id==v1.id
        async with factory() as s: assert len((await s.scalars(select(StartupResearchNeedVersion).where(StartupResearchNeedVersion.need_id==n.id))).all())==2 and (await s.scalar(select(ResearchMatchRun).where(ResearchMatchRun.id==run.id))).need_version_id==v1.id
    finally:
        async with factory() as s:
            if pid: await s.execute(delete(AuditLog).where(AuditLog.project_id==pid)); await s.execute(delete(ResearchMatchResult).where(ResearchMatchResult.run_id.in_(select(ResearchMatchRun.id).where(ResearchMatchRun.project_id==pid)))); await s.execute(delete(ResearchMatchRun).where(ResearchMatchRun.project_id==pid)); await s.execute(delete(StartupResearchNeedVersion).where(StartupResearchNeedVersion.need_id.in_(select(StartupResearchNeed.id).where(StartupResearchNeed.project_id==pid)))); await s.execute(delete(StartupResearchNeed).where(StartupResearchNeed.project_id==pid)); await s.execute(delete(ProjectMember).where(ProjectMember.project_id==pid)); await s.execute(delete(Project).where(Project.id==pid))
            await s.execute(delete(User).where(User.id==uid)); await s.commit()

@pytest.mark.asyncio
async def test_scrum211_api_need_version_match_and_idor(factory):
    uid=uuid.uuid4(); other=uuid.uuid4(); ea=f"scrum211-api-{uid}@example.test"; eb=f"scrum211-api-{other}@example.test"; pid=None
    async with factory() as s: s.add_all([User(id=uid,email=ea),User(id=other,email=eb)]); await s.commit()
    async def override_session():
        async with factory() as s: yield s
    app.dependency_overrides[get_session]=override_session; app.dependency_overrides[get_authenticated_principal]=lambda: actor(uid,ea)
    try:
        async with factory() as s: pid=(await ProjectService(s).create_idea(actor(uid,ea),IdeaProjectCreate(display_name="API matching"))).id
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c:
            n=await c.post(f"/projects/{pid}/research-needs",json={"domains":["manufacturing"],"technologies":["computer vision"],"research_problem":"surface defects","keywords":["inspection"]}); assert n.status_code==201; body=n.json(); v=await c.post(f"/projects/{pid}/research-needs/{body['id']}/versions",json={"domains":[],"technologies":[],"research_problem":"energy","keywords":[]}); assert v.status_code==201; run=await c.post(f"/projects/{pid}/research-needs/{body['id']}/match"); assert run.status_code==201 and run.json()["algorithm_id"]=="sparse_research_matching_s3"; assert (await c.get(f"/projects/{pid}/research-match-runs/{run.json()['id']}" )).status_code==200
        app.dependency_overrides[get_authenticated_principal]=lambda: actor(other,eb)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as c: assert (await c.get(f"/projects/{pid}/research-match-runs/{run.json()['id']}")).status_code==404
    finally:
        app.dependency_overrides.clear()
        async with factory() as s:
            if pid: await s.execute(delete(AuditLog).where(AuditLog.project_id==pid)); await s.execute(delete(ProjectMember).where(ProjectMember.project_id==pid)); await s.execute(delete(Project).where(Project.id==pid))
            await s.execute(delete(User).where(User.id.in_([uid,other]))); await s.commit()


@pytest.mark.asyncio
async def test_scrum211_persisted_e2e_projection_privacy_and_version_isolation(factory):
    uid = uuid.uuid4(); email = f"scrum211-e2e-{uid}@example.test"; pid = None
    discovery_ids = []
    async with factory() as s:
        s.add(User(id=uid, email=email)); await s.commit()
    try:
        async with factory() as s:
            principal = actor(uid, email)
            pid = (await ProjectService(s).create_idea(principal, IdeaProjectCreate(display_name="E2E matching"))).id
            profile = ResearcherProfile(user_id=uid, scientific_domains=["engineering"])
            s.add(profile); await s.flush()

            async def add_snapshot(label, fields, visibility, status="APPROVED"):
                output = ResearchOutput(researcher_profile_id=profile.id, title=f"{label} output", authors=["Researcher"], rights_holder="Researcher", licence="CC-BY", visibility="public", rights_metadata_status="COMPLETE", publication_ready=True)
                s.add(output); await s.flush()
                doc = Document(owner_user_id=uid, title=f"{label} source", document_type="txt", classification="public", visibility="public", processing_status="uploaded")
                s.add(doc); await s.flush()
                doc_version = DocumentVersion(document_id=doc.id, version_number=1, original_filename=f"{label}.txt", storage_key=f"scrum211/{uid}/{label}.txt", mime_type="text/plain", size_bytes=1, sha256=(label.lower().ljust(64, "0"))[:64], malware_scan_status="clean", uploaded_by_user_id=uid)
                s.add(doc_version); await s.flush(); doc.current_version_id = doc_version.id
                output_version = ResearchOutputVersion(research_output_id=output.id, document_version_id=doc_version.id, version_number=1, uploaded_by_user_id=uid, content_hash=(label.lower().ljust(64, "1"))[:64])
                s.add(output_version); await s.flush()
                extraction = ResearchExtractionRun(owner_user_id=uid, research_output_id=output.id, research_output_version_id=output_version.id, document_version_id=doc_version.id, source_sha256=doc_version.sha256, strategy="extractive_evidence_locked", strategy_version="4", provider="fixture", model="fixture", prompt_version="fixture", schema_version="1", segmenter_version="1", status="GENERATED")
                s.add(extraction); await s.flush()
                discovery = ResearchDiscovery(research_output_id=output.id, owner_user_id=uid)
                s.add(discovery); await s.flush(); discovery_ids.append(discovery.id)
                version = ResearchDiscoveryVersion(discovery_id=discovery.id, version_number=1, extraction_run_id=extraction.id, research_output_version_id=output_version.id, document_version_id=doc_version.id, source_sha256=doc_version.sha256, content={"fields": fields, "evidence": {}, "abstract": "fixture"}, visibility=visibility, status=status, approved_by_user_id=uid if status == "APPROVED" else None)
                s.add(version); await s.flush()
                if status == "APPROVED": version.approved_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                return version

            matchable = {"domains": "MATCHABLE", "technologies": "MATCHABLE", "research_problem": "MATCHABLE", "keywords": "MATCHABLE", "abstract": "PRIVATE"}
            r1 = await add_snapshot("R1", {"domains": ["industrial manufacturing"], "technologies": ["computer vision"], "research_problem": ["inspection and detection of defects on manufactured surfaces"], "keywords": ["inspection", "defects", "vision"]}, matchable)
            r2 = await add_snapshot("R2", {"domains": ["marine biology"], "technologies": ["computer vision"], "research_problem": ["classification of marine species from underwater imagery"], "keywords": ["vision", "classification", "species"]}, matchable)
            r3 = await add_snapshot("R3", {"domains": ["industrial manufacturing"], "technologies": [], "research_problem": ["visual inspection of manufactured components"], "keywords": ["inspection"]}, matchable)
            r4 = await add_snapshot("R4", {"domains": ["industrial manufacturing"], "technologies": ["computer vision"], "research_problem": ["RB_DRAFT_ONLY_Q77Z computer vision detection of microscopic manufacturing surface defects"], "keywords": ["RB_DRAFT_ONLY_Q77Z"]}, matchable, "DRAFT")
            r5 = await add_snapshot("R5", {"domains": ["marine biology"], "technologies": ["statistics"], "research_problem": ["unrelated ocean survey", "RB_PRIVATE_SENTINEL_X91Q"], "keywords": ["ocean"]}, {**matchable, "research_problem": "PRIVATE"})
            r6 = await add_snapshot("R6", {"domains": ["generic"], "technologies": ["AI model"], "research_problem": ["generic data network"], "keywords": ["AI", "data", "network"]}, matchable)
            await s.commit()

        async with factory() as s:
            rows = (await s.scalars(select(ResearchDiscoveryVersion).where(ResearchDiscoveryVersion.id.in_([r1.id, r2.id, r3.id, r4.id, r5.id, r6.id])))).all()
            by_id = {row.id: row for row in rows}
            assert by_id[r1.id].status == "APPROVED" and by_id[r1.id].visibility["research_problem"] == "MATCHABLE"
            assert by_id[r4.id].status == "DRAFT"
            assert by_id[r5.id].visibility["research_problem"] == "PRIVATE"
            assert "RB_PRIVATE_SENTINEL_X91Q" in str(by_id[r5.id].content)

            principal = actor(uid, email)
            need, v1 = await ResearchMatchingService(s).create_need(principal, pid, ResearchNeedPayload(domains=["industrial manufacturing"], technologies=["computer vision"], research_problem="detect microscopic defects on manufactured surfaces", keywords=["inspection", "defects", "vision"]))
            run1 = await ResearchMatchingService(s).run(principal, pid, need.id, v1.id)
            loaded1 = await ResearchMatchingService(s).get_run(principal, pid, run1.id)
            result_ids = {item.research_discovery_version_id for item in loaded1.results}
            assert r1.id in result_ids and r2.id not in result_ids and r4.id not in result_ids and r6.id not in result_ids
            positive = next(item for item in loaded1.results if item.research_discovery_version_id == r1.id)
            assert positive.rank >= 1 and positive.reason_codes and positive.startup_field_refs and positive.research_field_refs and positive.uncertainty_codes == []
            assert all(ref in {"domains", "technologies", "research_problem", "keywords"} for ref in positive.research_field_refs)
            assert "RB_DRAFT_ONLY_Q77Z" not in str(loaded1)

            research_v2 = ResearchDiscoveryVersion(discovery_id=r1.discovery_id, version_number=2, extraction_run_id=r1.extraction_run_id, research_output_version_id=r1.research_output_version_id, document_version_id=r1.document_version_id, source_sha256=r1.source_sha256, content={"fields": {"domains": ["industrial manufacturing"], "technologies": ["computer vision"], "research_problem": ["computer vision detection of microscopic manufacturing surface defects"], "keywords": ["inspection", "defects", "vision"]}, "evidence": {}, "abstract": "fixture"}, visibility=matchable, status="DRAFT")
            s.add(research_v2); await s.flush()
            assert research_v2.status == "DRAFT"
            await DiscoveryService(s).approve(principal, r1.discovery_id, research_v2.id)
            assert (await s.scalar(select(ResearchDiscoveryVersion).where(ResearchDiscoveryVersion.id == research_v2.id))).status == "APPROVED"
            future_need, future_version = await ResearchMatchingService(s).create_need(principal, pid, ResearchNeedPayload(domains=["industrial manufacturing"], technologies=["computer vision"], research_problem="detect microscopic defects on manufactured surfaces", keywords=["inspection", "defects", "vision"]))
            future_run = await ResearchMatchingService(s).run(principal, pid, future_need.id, future_version.id)
            future_results = await ResearchMatchingService(s).get_run(principal, pid, future_run.id)
            assert any(item.research_discovery_version_id == research_v2.id for item in future_results.results)
            historical = await ResearchMatchingService(s).get_run(principal, pid, run1.id)
            assert {item.research_discovery_version_id for item in historical.results} == result_ids

            partial_need, partial_version = await ResearchMatchingService(s).create_need(principal, pid, ResearchNeedPayload(domains=["industrial manufacturing"], technologies=[], research_problem="detect microscopic defects on manufactured surfaces", keywords=["inspection", "defects"]))
            partial_run = await ResearchMatchingService(s).run(principal, pid, partial_need.id, partial_version.id)
            partial_result = next(item for item in (await ResearchMatchingService(s).get_run(principal, pid, partial_run.id)).results if item.research_discovery_version_id == r1.id)
            assert "MISSING_STARTUP_TECHNOLOGY" in partial_result.uncertainty_codes
            assert "TECHNOLOGY_LEXICAL_ALIGNMENT" not in partial_result.reason_codes

            _, v2 = await ResearchMatchingService(s).version_need(principal, pid, need.id, ResearchNeedPayload(domains=["energy"], technologies=[], research_problem="energy demand forecasting", keywords=[]))
            run2 = await ResearchMatchingService(s).run(principal, pid, need.id, v2.id)
            assert run1.need_version_id == v1.id and run2.need_version_id == v2.id
            assert (await ResearchMatchingService(s).get_run(principal, pid, run1.id)).need_version_id == v1.id

            no_need, no_version = await ResearchMatchingService(s).create_need(principal, pid, ResearchNeedPayload(domains=["astronomy"], technologies=["radio telescope"], research_problem="distant galaxy spectroscopy", keywords=["galaxy"]))
            empty = await ResearchMatchingService(s).run(principal, pid, no_need.id, no_version.id)
            assert empty.status == "COMPLETED" and (await ResearchMatchingService(s).get_run(principal, pid, empty.id)).results == []

            async def override_session():
                async with factory() as request_session:
                    yield request_session
            app.dependency_overrides[get_session] = override_session
            app.dependency_overrides[get_authenticated_principal] = lambda: principal
            assert await s.scalar(select(func.count()).select_from(ResearchDiscoveryVersion).where(ResearchDiscoveryVersion.status == "APPROVED")) >= 5
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                api_need = await client.post(f"/projects/{pid}/research-needs", json={"domains": ["industrial manufacturing"], "technologies": ["computer vision"], "research_problem": "inspection of manufactured surfaces", "keywords": ["inspection"]})
                assert api_need.status_code == 201
                api_run = await client.post(f"/projects/{pid}/research-needs/{api_need.json()['id']}/match")
                assert api_run.status_code == 201 and api_run.json()["results"]
                assert any(item["research_discovery_version_id"] == str(r1.id) for item in api_run.json()["results"])
                assert any(item["uncertainty_codes"] == [] for item in api_run.json()["results"] if item["research_discovery_version_id"] == str(r1.id))
                assert "RB_PRIVATE_SENTINEL_X91Q" not in api_run.text and "RB_DRAFT_ONLY_Q77Z" not in api_run.text
            app.dependency_overrides.pop(get_authenticated_principal, None)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                unauthenticated = await client.post(f"/projects/{pid}/research-needs", json={"domains": ["x"], "technologies": [], "research_problem": "x", "keywords": []})
                assert unauthenticated.status_code in {401, 403}
            app.dependency_overrides.clear()
    finally:
        app.dependency_overrides.clear()
        async with factory() as s:
            if pid:
                await s.execute(delete(AuditLog).where(AuditLog.project_id == pid))
                await s.execute(delete(ResearchMatchResult).where(ResearchMatchResult.run_id.in_(select(ResearchMatchRun.id).where(ResearchMatchRun.project_id == pid))))
                await s.execute(delete(ResearchMatchRun).where(ResearchMatchRun.project_id == pid))
                await s.execute(delete(StartupResearchNeedVersion).where(StartupResearchNeedVersion.need_id.in_(select(StartupResearchNeed.id).where(StartupResearchNeed.project_id == pid))))
                await s.execute(delete(StartupResearchNeed).where(StartupResearchNeed.project_id == pid))
                await s.execute(delete(ProjectMember).where(ProjectMember.project_id == pid)); await s.execute(delete(Project).where(Project.id == pid))
            if discovery_ids:
                await s.execute(delete(ResearchDiscoveryVersion).where(ResearchDiscoveryVersion.discovery_id.in_(discovery_ids)))
                await s.execute(delete(ResearchDiscovery).where(ResearchDiscovery.id.in_(discovery_ids)))
            await s.execute(delete(AuditLog).where(AuditLog.actor_user_id == uid))
            await s.execute(delete(ResearchExtractionRun).where(ResearchExtractionRun.owner_user_id == uid))
            await s.execute(delete(ResearchOutputVersion).where(ResearchOutputVersion.uploaded_by_user_id == uid))
            await s.execute(delete(ResearchOutput).where(ResearchOutput.researcher_profile_id.in_(select(ResearcherProfile.id).where(ResearcherProfile.user_id == uid))))
            await s.execute(delete(ResearcherProfile).where(ResearcherProfile.user_id == uid))
            await s.execute(delete(DocumentVersion).where(DocumentVersion.uploaded_by_user_id == uid)); await s.execute(delete(Document).where(Document.owner_user_id == uid))
            await s.execute(delete(User).where(User.id == uid)); await s.commit()
