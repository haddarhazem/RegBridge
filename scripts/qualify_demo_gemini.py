"""Run one bounded, opt-in Gemini demo-provider qualification request.

Each invocation performs exactly one provider call and emits only safe metadata.
It never prints prompts, generated text, credentials, headers, or response bodies.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings
from app.modules.ai.llm import LLMGenerationRequest, LLMMessage, LLMProviderError
from app.modules.ai.providers.gemini import GeminiLLMProvider
from app.modules.regulatory.contracts import RegulatoryEvidence
from app.modules.regulatory.verification import SemanticVerifier


ALLOWED_MODELS = ("gemini-3.5-flash-lite", "gemini-3.5-flash")


class _TinyStructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool


def _provider(model: str) -> GeminiLLMProvider:
    settings = get_settings()
    return GeminiLLMProvider(
        api_key=settings.gemini_api_key,
        model=model,
        # Qualification is intentionally a single attempt. Production retry and
        # pacing settings remain unchanged and are exercised only after selection.
        max_attempts=1,
        min_request_interval_seconds=0,
    )


def _safe_error(stage: str, model: str, exc: LLMProviderError) -> dict[str, object]:
    return {
        "stage": stage,
        "model": model,
        "result": "FAIL",
        "category": exc.category,
        "http_status": exc.http_status,
        "rate_limit_classification": getattr(exc, "rate_limit_classification", None),
    }


async def _plain(model: str) -> dict[str, object]:
    response = await _provider(model).generate(
        LLMGenerationRequest(
            messages=[LLMMessage(role="user", content="Réponds seulement OK.")],
            temperature=0,
            max_tokens=32,
            prompt_version="demo-provider-qualification-v1",
            operation="demo_provider_plain_qualification",
        )
    )
    valid = response.content.strip().rstrip(".").casefold() == "ok"
    if not valid:
        raise ValueError("plain response did not satisfy the exact local assertion")
    return {
        "stage": "plain",
        "model": model,
        "result": "PASS",
        "content_valid": True,
        "duration_ms": response.execution.duration_ms if response.execution else None,
        "usage": response.usage,
    }


async def _tiny_structured(model: str) -> dict[str, object]:
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "DemoProviderTinyOutput",
            "schema": _TinyStructuredOutput.model_json_schema(),
        },
    }
    response = await _provider(model).generate(
        LLMGenerationRequest(
            messages=[LLMMessage(role="user", content="Retourne un objet JSON où ok vaut true.")],
            temperature=0,
            max_tokens=64,
            response_format=schema,
            prompt_version="demo-provider-qualification-v1",
            operation="demo_provider_tiny_structured_qualification",
        )
    )
    parsed = _TinyStructuredOutput.model_validate_json(response.content)
    if parsed.ok is not True:
        raise ValueError("tiny structured response did not satisfy the local assertion")
    return {
        "stage": "tiny-structured",
        "model": model,
        "result": "PASS",
        "schema_valid": True,
        "duration_ms": response.execution.duration_ms if response.execution else None,
        "usage": response.usage,
    }


async def _semantic(model: str) -> dict[str, object]:
    output, execution = await SemanticVerifier(_provider(model), max_tokens=300).verify(
        question="Quelle obligation est décrite dans l'extrait ?",
        answer="L'entreprise doit informer les personnes de la finalité du traitement.",
        evidence=[
            RegulatoryEvidence(
                point_id="demo-evidence-1",
                rank=1,
                retrieval_score=1.0,
                organization="Organisation de démonstration",
                source_domain="example.invalid",
                chunk_index=0,
                content="L'entreprise informe les personnes concernées de la finalité du traitement.",
            )
        ],
    )
    # SemanticVerifier has already performed exact SemanticVerificationOutput
    # validation. Re-validate the dumped object to make the qualification gate
    # explicit and independent from provider hints.
    output.__class__.model_validate(output.model_dump())
    return {
        "stage": "semantic",
        "model": model,
        "result": "PASS",
        "schema": "SemanticVerificationOutput",
        "schema_valid": True,
        "verdict": output.verdict,
        "duration_ms": execution.duration_ms if execution else None,
        "usage": {
            "prompt_tokens": execution.prompt_tokens if execution else None,
            "completion_tokens": execution.completion_tokens if execution else None,
            "total_tokens": execution.total_tokens if execution else None,
        },
    }


async def _run(stage: Literal["plain", "tiny-structured", "semantic"], model: str) -> int:
    get_settings.cache_clear()
    settings = get_settings()
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value():
        print(json.dumps({"stage": stage, "model": model, "result": "FAIL", "category": "credential_missing"}))
        return 2
    try:
        result = await {
            "plain": _plain,
            "tiny-structured": _tiny_structured,
            "semantic": _semantic,
        }[stage](model)
    except LLMProviderError as exc:
        print(json.dumps(_safe_error(stage, model, exc)))
        return 2
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({
            "stage": stage,
            "model": model,
            "result": "FAIL",
            "category": "local_validation_failed",
            "cause_type": type(exc).__name__,
        }))
        return 3
    print(json.dumps(result))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("plain", "tiny-structured", "semantic"))
    parser.add_argument("--model", choices=ALLOWED_MODELS, default=ALLOWED_MODELS[0])
    args = parser.parse_args()
    return asyncio.run(_run(args.stage, args.model))


if __name__ == "__main__":
    raise SystemExit(main())
