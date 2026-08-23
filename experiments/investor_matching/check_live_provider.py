"""Opt-in provider connectivity check for EX-021; never runs the holdout."""

from __future__ import annotations

import asyncio
import os

from app.core.config import get_settings
from app.modules.ai.llm import LLMGenerationRequest, LLMMessage, LLMProviderError
from app.modules.ai.providers.mistral import get_mistral_provider


async def check() -> int:
    settings = get_settings()
    provider = get_mistral_provider()
    response = await provider.generate(LLMGenerationRequest(
        messages=[
            LLMMessage(role="system", content="Return a short JSON object with one key named status."),
            LLMMessage(role="user", content="Return status=ok. This is a connectivity check, not a benchmark case."),
        ],
        temperature=0,
        max_tokens=30,
        prompt_version="scrum203-provider-connectivity-v1",
        operation="scrum203_provider_connectivity",
    ))
    execution = response.execution
    print("Provider: mistral")
    print(f"Model configured: {'YES' if settings.mistral_model else 'NO'}")
    print("Minimal live request: PASS")
    print(f"Response metadata available: {'YES' if execution is not None else 'NO'}")
    return 0


def main() -> int:
    if os.getenv("EX021_LIVE") != "1":
        print("EX021_LIVE opt-in required; live request not run")
        return 2
    try:
        return asyncio.run(check())
    except LLMProviderError as exc:
        print(f"Minimal live request: FAIL ({exc.category})")
        return 1
    except Exception as exc:
        print(f"Minimal live request: FAIL ({type(exc).__name__})")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
