from __future__ import annotations

import json
import time
from typing import Any

from app.modules.ai.llm import LLMGenerationRequest, LLMMessage, LLMProvider

from .contracts import ExtractionResponse

ALLOWED_DOMAINS = ["activity", "sector", "technology", "data", "market", "location"]
PROMPT_VERSION = "scrum188-ex005-fact-extraction-v1"

FACT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "domain": {"type": "string", "enum": ALLOWED_DOMAINS},
                    "value": {"type": "string"},
                    "origin": {"type": "string", "enum": ["inferred"]},
                    "status": {"type": "string", "enum": ["pending_confirmation"]},
                    "provenance": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "source_field": {"type": "string", "enum": ["description"]},
                            "excerpt": {"type": "string"},
                            "rule": {"type": ["string", "null"]},
                        },
                        "required": ["source_field", "excerpt", "rule"],
                    },
                    "uncertainty": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["domain", "value", "origin", "status", "provenance", "uncertainty"],
            },
        }
    },
    "required": ["facts"],
}


def build_request(description: str) -> LLMGenerationRequest:
    return LLMGenerationRequest(
        messages=[
            LLMMessage(role="system", content=(
                "Extract only project facts explicitly supported by the input. "
                "Return JSON matching the requested schema. Use only the allowed domains. "
                "Respect negation, preserve ambiguity with medium or low uncertainty, "
                "never infer legal conclusions or protected attributes, and do not coach the business. "
                "Each fact must cite a short exact supporting excerpt from the input."
            )),
            LLMMessage(role="user", content=json.dumps({"description": description, "allowed_domains": ALLOWED_DOMAINS}, ensure_ascii=False)),
        ],
        temperature=0,
        max_tokens=1200,
        response_format={"type": "json_schema", "json_schema": {"name": "project_facts", "schema": FACT_SCHEMA}},
        prompt_version=PROMPT_VERSION,
        operation="scrum188_fact_extraction",
    )


async def extract(provider: LLMProvider, description: str) -> tuple[ExtractionResponse | None, dict[str, Any]]:
    started = time.perf_counter()
    response = await provider.generate(build_request(description))
    duration_ms = (time.perf_counter() - started) * 1000
    try:
        parsed = ExtractionResponse.model_validate_json(response.content)
    except Exception:
        return None, {"valid": False, "latency_ms": duration_ms, "usage": response.usage}
    return parsed, {"valid": True, "latency_ms": duration_ms, "usage": response.usage}
