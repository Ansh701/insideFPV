import json
from abc import abstractmethod
from collections.abc import Mapping
from typing import Any

import httpx

from app.services.llm.base import LLMProvider, ProviderFailure


def extract_json_object(text: str) -> Mapping[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```")
        stripped = stripped.removesuffix("```").strip()
    start, end = stripped.find("{"), stripped.rfind("}")
    if start < 0 or end < start:
        raise ProviderFailure(
            "Provider returned no JSON object.", retryable=True, category="INVALID_OUTPUT"
        )
    try:
        value = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ProviderFailure(
            "Provider returned invalid JSON.", retryable=True, category="INVALID_OUTPUT"
        ) from exc
    if not isinstance(value, dict):
        raise ProviderFailure(
            "Provider JSON must be an object.", retryable=True, category="INVALID_OUTPUT"
        )
    return value


class HttpLLMProvider(LLMProvider):
    def __init__(self, api_key: str | None, model: str, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.is_configured = bool(api_key)

    async def generate_json(self, purpose: str, prompt: str) -> Mapping[str, Any]:
        if not self.api_key:
            raise ProviderFailure(
                "Provider is not configured.", retryable=False, category="NOT_CONFIGURED"
            )
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await self._request(client, purpose, prompt)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderFailure(
                "Provider timed out.", retryable=True, category="TIMEOUT"
            ) from exc
        except httpx.NetworkError as exc:
            raise ProviderFailure(
                "Provider network request failed.", retryable=True, category="NETWORK"
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in {401, 403, 408, 409, 429} or status >= 500:
                category = "RATE_LIMIT" if status == 429 else "UPSTREAM"
                raise ProviderFailure(
                    f"Provider request failed with HTTP {status}.",
                    retryable=True,
                    category=category,
                ) from exc
            raise ValueError(f"LLM request construction was rejected with HTTP {status}.") from exc
        try:
            response_text = self._response_text(response.json())
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderFailure(
                "Provider returned an unexpected response envelope.",
                retryable=True,
                category="INVALID_OUTPUT",
            ) from exc
        return extract_json_object(response_text)

    @abstractmethod
    async def _request(
        self, client: httpx.AsyncClient, purpose: str, prompt: str
    ) -> httpx.Response:
        raise NotImplementedError

    @abstractmethod
    def _response_text(self, payload: Mapping[str, Any]) -> str:
        raise NotImplementedError
