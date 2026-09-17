"""Regression protection for defects first reproduced through the real demo UI."""
import json
import uuid

import pytest

from app.modules.ai.contracts import AgentRequest, AuthorizedContext
from app.modules.ai.llm import LLMGenerationResponse
from app.modules.regulatory.agent import RegulatoryAgent
from app.modules.regulatory.assessment_service import RegulatoryAssessmentService
from app.modules.regulatory.contracts import RegulatoryEvidence
from app.modules.regulatory.roadmap_generation import generate_typed_items
from app.modules.regulatory.verification import VerificationResult


class Retriever:
    async def retrieve(self, question):
        return [RegulatoryEvidence(point_id='evidence-1', organization='Synthetic authority', rank=1, retrieval_score=1, content='Synthetic regulatory evidence')]


class Provider:
    def __init__(self, content):
        self.content = content
        self.request = None

    async def generate(self, request):
        self.request = request
        return LLMGenerationResponse(content=self.content, model='synthetic')


class Verifier:
    def __init__(self, verdict='pass'):
        self.answer = None
        self.verdict = verdict

    async def verify(self, **kwargs):
        self.answer = kwargs['answer']
        return VerificationResult(verdict=self.verdict, latency_ms=0)


def request():
    return AgentRequest(request_id=uuid.uuid4(), parent_run_id=uuid.uuid4(), question='Évaluez les obligations applicables.', capability='regulatory', locale='fr', authorized_context=AuthorizedContext())


@pytest.mark.asyncio
async def test_assessment_populates_existing_consumers_and_verifies_all_conclusions():
    draft = {'answer':'Synthèse.', 'obligations':['Obligation synthétique.'], 'recommendations':['Préparation synthétique.'], 'missing_information':['Périmètre à préciser.']}
    provider, verifier = Provider(json.dumps(draft)), Verifier()
    result = await RegulatoryAgent(retriever=Retriever(), provider=provider, verifier=verifier, structured_assessment=True).run(request())
    assert provider.request.response_format['type'] == 'json_schema'
    assert result.findings == draft['obligations']
    assert result.recommendations == draft['recommendations']
    assert result.missing_information == draft['missing_information']
    assert all(value in verifier.answer for key in ('obligations','recommendations','missing_information') for value in draft[key])
    payload, evidence = RegulatoryAssessmentService._result_payload(result)
    roadmap_items = generate_typed_items(payload.model_dump())
    assert any(item["title"] == draft["obligations"][0] for item in roadmap_items)
    assert any(item["title"] == draft["recommendations"][0] for item in roadmap_items)
    assert not any(item["title"] == draft["missing_information"][0] for item in roadmap_items)
    assert payload.obligations[0].source_refs == ['evidence-1']
    assert evidence[0]['point_id'] == 'evidence-1'


@pytest.mark.asyncio
@pytest.mark.parametrize('content', ['Unstructured prose', '{"answer":"Missing collections"}', '{"answer":"x","obligations":[""],"recommendations":[],"missing_information":[]}'])
async def test_invalid_assessment_contract_fails_closed(content):
    verifier = Verifier()
    result = await RegulatoryAgent(retriever=Retriever(), provider=Provider(content), verifier=verifier, structured_assessment=True).run(request())
    assert result.status == 'failed'
    assert result.error_code == 'invalid_assessment_output'
    assert verifier.answer is None


@pytest.mark.asyncio
async def test_structured_generation_does_not_override_verifier_block():
    content=json.dumps({'answer':'Unsupported.', 'obligations':['Unsupported requirement.'], 'recommendations':[], 'missing_information':[]})
    result=await RegulatoryAgent(retriever=Retriever(), provider=Provider(content), verifier=Verifier('block'), structured_assessment=True).run(request())
    assert result.structured_payload['verification_verdict']=='block'
