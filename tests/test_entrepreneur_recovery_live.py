"""Bounded, explicitly opt-in Gemini recovery checks, not a benchmark."""
import json
import os

import pytest

from app.core.config import get_settings
from app.modules.ai.llm import LLMGenerationRequest, LLMMessage
from app.modules.ai.providers.selection import get_llm_provider

pytestmark = pytest.mark.skipif(os.getenv('ENTREPRENEUR_LIVE') != '1', reason='Explicit live recovery authorization required')


@pytest.mark.asyncio
async def test_gemini_plain_and_structured_connectivity():
    assert get_settings().llm_provider == 'gemini'
    provider = get_llm_provider()
    plain = await provider.generate(LLMGenerationRequest(
        messages=[LLMMessage(role='user', content='Réponds seulement OK.')], max_tokens=32,
        operation='recovery_smoke',
    ))
    assert plain.content.strip().strip('.') == 'OK'
    structured = await provider.generate(LLMGenerationRequest(
        messages=[LLMMessage(role='user', content='Réponds avec un objet JSON contenant ok: true.')],
        max_tokens=64, operation='recovery_structured_smoke',
        response_format={'type': 'json_schema', 'json_schema': {'name': 'Smoke', 'strict': True, 'schema': {
            'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok'], 'additionalProperties': False,
        }}},
    ))
    assert json.loads(structured.content) == {'ok': True}
    print(json.dumps({'plain': 'PASS', 'structured': 'PASS', 'model': plain.model,
                      'plain_usage': plain.usage, 'structured_usage': structured.usage}))
