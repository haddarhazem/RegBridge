"""Developer-only synthetic Mistral provider smoke test; no benchmark data."""

from __future__ import annotations

import asyncio
import time

from app.modules.ai.llm import LLMGenerationRequest, LLMMessage
from app.modules.ai.providers.mistral import get_mistral_provider


async def main() -> None:
    provider = get_mistral_provider()
    request = LLMGenerationRequest(
        messages=[LLMMessage(role="user", content="Réponds uniquement par le mot OK.")],
        temperature=0,
        max_tokens=8,
    )
    started = time.perf_counter()
    try:
        response = await provider.generate(request)
    except Exception as exc:
        print("Provider smoke: FAIL")
        print(f"Exception class: {type(exc).__name__}")
        print(f"Latency ms: {(time.perf_counter() - started) * 1000:.2f}")
        return
    print("Provider smoke: PASS")
    print(f"Model configured/accepted: {'yes' if response.model else 'no'}")
    print(f"Latency ms: {(time.perf_counter() - started) * 1000:.2f}")
    print(f"Response length: {len(response.content)}")
    print(f"Usage keys: {sorted(response.usage)}")


if __name__ == "__main__":
    asyncio.run(main())
