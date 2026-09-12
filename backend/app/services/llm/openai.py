from collections.abc import Mapping
from typing import Any

import httpx

from app.services.llm.http_provider import HttpLLMProvider


class OpenAIProvider(HttpLLMProvider):
    name = "openai"

    async def _request(
        self, client: httpx.AsyncClient, purpose: str, prompt: str
    ) -> httpx.Response:
        return await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
        )

    def _response_text(self, payload: Mapping[str, Any]) -> str:
        return str(payload["choices"][0]["message"]["content"])
