from app.config import Settings
from app.services.llm.anthropic import AnthropicProvider
from app.services.llm.gemini import GeminiProvider
from app.services.llm.openai import OpenAIProvider
from app.services.llm.service import LLMService


def build_llm_service(settings: Settings) -> LLMService:
    providers = [
        GeminiProvider(
            settings.gemini_api_key, settings.gemini_model, settings.llm_provider_timeout_seconds
        ),
        OpenAIProvider(
            settings.openai_api_key, settings.openai_model, settings.llm_provider_timeout_seconds
        ),
        AnthropicProvider(
            settings.anthropic_api_key,
            settings.anthropic_model,
            settings.llm_provider_timeout_seconds,
        ),
    ]
    return LLMService(
        providers,
        timeout_seconds=settings.llm_provider_timeout_seconds,
        max_retries=settings.llm_max_retries,
        cooldown_seconds=settings.llm_provider_cooldown_seconds,
    )
