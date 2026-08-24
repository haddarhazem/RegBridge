import importlib.util
import json
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.investment.brief_service import OpportunityBriefService
from app.modules.investment.brief_models import InvestorOpportunityBriefRun
from app.modules.investment.brief_verification import verify_frozen_brief
from app.modules.investment.brief_verification_models import BriefClaimVerification, BriefVerificationRun
from app.modules.investment.models import InvestorThesisVersion
from app.modules.projects.models import Project
from app.modules.ai.llm import LLMExecutionMetadata, LLMGenerationResponse
from app.modules.investment.brief_semantic_verification import verify_semantically

_spec = importlib.util.spec_from_file_location("scrum203_fixtures", Path(__file__).with_name("test_scrum203_matching.py"))
_fixtures = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fixtures)
cleanup = _fixtures.cleanup
make_fixture = _fixtures.make_fixture
make_user = _fixtures.make_user


@pytest_asyncio.fixture
async def verification_factory():
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"PostgreSQL unavailable for SCRUM-205: {exc}")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


def test_deterministic_verifier_blocks_mutations_and_unknown_as_match():
    bundle = {"confirmed_facts": [{"domain": "fundraising_target", "value": 300000, "status": "confirmed", "evidence_ref": "fact:funding"}], "evidence_refs": ["fact:funding", "matching:run:stage"], "matching_result": {"dimensions": {"stage": "UNKNOWN"}}}
    assert verify_frozen_brief({"claims": [{"text": "fundraising_target: 500000", "evidence_refs": ["fact:funding"]}]}, bundle, bundle["matching_result"])[0].verdict == "UNSUPPORTED"
    assert verify_frozen_brief({"thesis_fit": ["stage: MATCH"]}, bundle, bundle["matching_result"])[0].reason_code == "matching_outcome_changed"
    assert verify_frozen_brief({"claims": [{"text": "fundraising_target: 300000", "evidence_refs": ["wrong:ref"]}]}, bundle, bundle["matching_result"])[0].verdict == "UNSUPPORTED"


@pytest.mark.asyncio
async def test_semantic_fallback_is_structured_and_allowlisted():
    class Provider:
        async def generate(self, request):
            return LLMGenerationResponse(content=json.dumps({"status": "SUPPORTED", "reason_code": "faithful_paraphrase", "evidence_refs": ["fact:location"]}), model="test", execution=LLMExecutionMetadata(provider="test", logical_model="test", model="test", status="success"))

    verdict, execution, error = await verify_semantically(Provider(), claim="operates in the French market", claim_type="faithful_paraphrase", evidence={"confirmed_facts": [{"domain": "location", "value": "France"}]}, evidence_refs=["fact:location"])
    assert verdict is not None and verdict.status == "SUPPORTED" and execution is not None and error is None


@pytest.mark.asyncio
async def test_semantic_fallback_rejects_unallowed_evidence():
    class Provider:
        async def generate(self, request):
            return LLMGenerationResponse(content=json.dumps({"status": "SUPPORTED", "reason_code": "invented", "evidence_refs": ["private:secret"]}), model="test")

    verdict, _, error = await verify_semantically(Provider(), claim="customers: 12", claim_type="customers", evidence={}, evidence_refs=[])
    assert verdict is None and error == "unsupported_evidence_reference"


@pytest.mark.asyncio
async def test_verification_persists_claims_and_uses_frozen_brief(verification_factory):
    investor, startup, version_id, project_id, revision_id = await make_fixture(verification_factory)
    other = await make_user(verification_factory, "verification-other")
    try:
        async with verification_factory() as session:
            brief = await OpportunityBriefService(session).create(investor, project_id, version_id)
            result = await OpportunityBriefService(session).verify(investor, brief.id)
            assert result.status == "VERIFIED"
            assert result.verifier_strategy == "deterministic_first_semantic_fallback"
            assert result.claims
            project = await session.get(Project, project_id)
            project.sector = "fintech"
            thesis = await session.get(InvestorThesisVersion, version_id)
            thesis.sectors = ["fintech"]
            await session.commit()
            stored_run = await session.get(BriefVerificationRun, result.id)
            stored_claims = list((await session.scalars(__import__("sqlalchemy").select(BriefClaimVerification).where(BriefClaimVerification.verification_run_id == result.id))).all())
            assert stored_run.brief_run_id == brief.id and stored_claims
            assert all(claim.verdict == "SUPPORTED" for claim in stored_claims)
        async with verification_factory() as session:
            historical = await OpportunityBriefService(session).get(investor, brief.id)
            assert historical.status == "VERIFIED"
            with pytest.raises(HTTPException):
                await OpportunityBriefService(session).verify(other, brief.id)
    finally:
        async with verification_factory() as session:
            verification_ids = list((await session.scalars(select(BriefVerificationRun.id).join(InvestorOpportunityBriefRun, BriefVerificationRun.brief_run_id == InvestorOpportunityBriefRun.id).where(InvestorOpportunityBriefRun.investor_user_id.in_([investor.user_id, startup.user_id, other.user_id])))).all())
            await session.execute(delete(BriefClaimVerification).where(BriefClaimVerification.verification_run_id.in_(verification_ids)))
            await session.execute(delete(BriefVerificationRun).where(BriefVerificationRun.id.in_(verification_ids)))
            await session.commit()
        await cleanup(verification_factory, [investor, startup, other], [project_id])
