from collections.abc import Mapping
from typing import Any

import httpx

from app.services.llm.http_provider import HttpLLMProvider


class AnthropicProvider(HttpLLMProvider):
    name = "anthropic"

    async def _request(
        self, client: httpx.AsyncClient, purpose: str, prompt: str
    ) -> httpx.Response:
        return await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": str(self.api_key),
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 700,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            },
        )

    def _response_text(self, payload: Mapping[str, Any]) -> str:
        return str(payload["content"][0]["text"])
