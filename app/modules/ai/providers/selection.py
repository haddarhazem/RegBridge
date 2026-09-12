"""Explicit configured selection of the production chat provider."""

from functools import lru_cache

from app.core.config import get_settings
from app.modules.ai.llm import LLMProvider
from app.modules.ai.providers.gemini import GeminiLLMProvider
from app.modules.ai.providers.http import DeepSeekLLMProvider, OllamaLLMProvider
from app.modules.ai.providers.mistral import get_mistral_provider


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "deepseek":
        return DeepSeekLLMProvider(api_key=settings.deepseek_api_key, model=settings.deepseek_model, base_url=settings.deepseek_base_url)
    if settings.llm_provider == "ollama":
        return OllamaLLMProvider(api_key=settings.ollama_api_key, model=settings.ollama_model, base_url=settings.ollama_base_url)
    if settings.llm_provider == "gemini":
        return GeminiLLMProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    return get_mistral_provider()
