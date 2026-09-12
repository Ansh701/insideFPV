import asyncio
from collections.abc import Mapping
from typing import Any

import httpx
import pytest

from app.models import ProductStatus
from app.services.llm.base import LLMProvider, ProviderFailure
from app.services.llm.http_provider import HttpLLMProvider
from app.services.llm.schemas import ChatIntentName, ProductExtraction
from app.services.llm.service import LLMService


class StubProvider(LLMProvider):
    def __init__(
        self,
        name: str,
        outcomes: list[Mapping[str, Any] | Exception],
        configured: bool = True,
        delay: float = 0,
    ) -> None:
        self.name = name
        self.model = f"{name}-small"
        self.is_configured = configured
        self.outcomes = list(outcomes)
        self.calls = 0
        self.delay = delay

    async def generate_json(self, purpose: str, prompt: str) -> Mapping[str, Any]:
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class MalformedEnvelopeProvider(HttpLLMProvider):
    name = "gemini"

    async def _request(
        self, client: httpx.AsyncClient, purpose: str, prompt: str
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={"unexpected": "provider schema"},
            request=httpx.Request("POST", "https://provider.invalid/generate"),
        )

    def _response_text(self, payload: Mapping[str, Any]) -> str:
        return str(payload["candidates"])


VALID = {
    "status": "IN_STOCK",
    "product_name": "Pixhawk 6X",
    "price": "25000.00",
    "currency": "INR",
    "manufacturer": "Holybro",
    "category": "Flight Controllers",
    "attributes": {},
    "compatibility": [],
    "confidence": 0.94,
    "evidence": ["Add to cart"],
}


@pytest.mark.asyncio
async def test_gemini_success_stops_failover_chain() -> None:
    gemini = StubProvider("gemini", [VALID])
    openai = StubProvider("openai", [VALID])
    anthropic = StubProvider("anthropic", [VALID])

    result = await LLMService([gemini, openai, anthropic], max_retries=0).classify_product("page")

    assert isinstance(result, ProductExtraction)
    assert result.provider == "gemini"
    assert (gemini.calls, openai.calls, anthropic.calls) == (1, 0, 0)


@pytest.mark.asyncio
async def test_gemini_rate_limit_falls_back_to_openai_only() -> None:
    gemini = StubProvider(
        "gemini", [ProviderFailure("rate limited", retryable=True, category="RATE_LIMIT")]
    )
    openai = StubProvider("openai", [VALID])
    anthropic = StubProvider("anthropic", [VALID])

    result = await LLMService([gemini, openai, anthropic], max_retries=0).classify_product("page")

    assert result.provider == "openai"
    assert (gemini.calls, openai.calls, anthropic.calls) == (1, 1, 0)


@pytest.mark.asyncio
async def test_two_provider_failures_reach_anthropic() -> None:
    failure = ProviderFailure("outage", retryable=True, category="UPSTREAM")
    providers = [
        StubProvider("gemini", [failure]),
        StubProvider("openai", [failure]),
        StubProvider("anthropic", [VALID]),
    ]

    result = await LLMService(providers, max_retries=0).classify_product("page")

    assert result.provider == "anthropic"
    assert [provider.calls for provider in providers] == [1, 1, 1]


@pytest.mark.asyncio
async def test_all_provider_failures_return_typed_unknown() -> None:
    providers = [
        StubProvider(name, [ProviderFailure("down", retryable=True, category="UPSTREAM")])
        for name in ("gemini", "openai", "anthropic")
    ]

    result = await LLMService(providers, max_retries=0).classify_product("ambiguous")

    assert result.status is ProductStatus.UNKNOWN
    assert result.provider is None
    assert result.classification_source == "FALLBACK"


@pytest.mark.asyncio
async def test_invalid_gemini_output_gets_one_repair_then_openai() -> None:
    gemini = StubProvider("gemini", [{"status": "maybe"}, {"still": "invalid"}])
    openai = StubProvider("openai", [VALID])

    result = await LLMService(
        [gemini, openai], max_retries=0, repair_invalid=True
    ).classify_product("page")

    assert result.provider == "openai"
    assert gemini.calls == 2
    assert openai.calls == 1


@pytest.mark.asyncio
async def test_unconfigured_gemini_is_skipped() -> None:
    gemini = StubProvider("gemini", [VALID], configured=False)
    openai = StubProvider("openai", [VALID])

    result = await LLMService([gemini, openai], max_retries=0).classify_product("page")

    assert result.provider == "openai"
    assert gemini.calls == 0


@pytest.mark.asyncio
async def test_only_anthropic_configured_is_used() -> None:
    providers = [
        StubProvider("gemini", [VALID], configured=False),
        StubProvider("openai", [VALID], configured=False),
        StubProvider("anthropic", [VALID]),
    ]

    result = await LLMService(providers, max_retries=0).classify_product("page")

    assert result.provider == "anthropic"


@pytest.mark.asyncio
async def test_no_provider_keeps_deterministic_system_available() -> None:
    result = await LLMService([], max_retries=0).classify_product("page")

    assert result.status is ProductStatus.UNKNOWN
    assert result.classification_source == "FALLBACK"


@pytest.mark.asyncio
async def test_timeout_moves_to_next_provider_without_hanging() -> None:
    slow = StubProvider("gemini", [VALID], delay=0.2)
    openai = StubProvider("openai", [VALID])

    result = await asyncio.wait_for(
        LLMService([slow, openai], timeout_seconds=0.01, max_retries=0).classify_product("page"),
        timeout=0.1,
    )

    assert result.provider == "openai"


@pytest.mark.asyncio
async def test_non_provider_programming_error_does_not_hide_bug_with_failover() -> None:
    gemini = StubProvider("gemini", [ValueError("bad request construction")])
    openai = StubProvider("openai", [VALID])

    with pytest.raises(ValueError, match="bad request construction"):
        await LLMService([gemini, openai], max_retries=0).classify_product("page")
    assert openai.calls == 0


@pytest.mark.asyncio
async def test_malformed_http_provider_envelope_fails_over() -> None:
    malformed = MalformedEnvelopeProvider("configured", "gemini-small", 1)
    openai = StubProvider("openai", [VALID])

    result = await LLMService([malformed, openai], max_retries=0).classify_product("page")

    assert result.provider == "openai"
    assert openai.calls == 1


@pytest.mark.asyncio
async def test_all_providers_normalize_to_same_product_schema() -> None:
    results = []
    for name in ("gemini", "openai", "anthropic"):
        results.append(
            await LLMService([StubProvider(name, [VALID])], max_retries=0).classify_product("page")
        )

    assert all(isinstance(result, ProductExtraction) for result in results)
    assert {result.status for result in results} == {ProductStatus.IN_STOCK}


@pytest.mark.asyncio
async def test_chat_intent_uses_same_ordered_provider_contract() -> None:
    intent = {
        "intent": "SEARCH_PRODUCTS",
        "query": "flight controllers",
        "availability": "IN_STOCK",
    }
    result = await LLMService([StubProvider("gemini", [intent])], max_retries=0).parse_chat_intent(
        "find one"
    )

    assert result.intent is ChatIntentName.SEARCH_PRODUCTS
    assert result.availability is ProductStatus.IN_STOCK
