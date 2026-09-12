from collections.abc import Mapping
from typing import Any

import httpx

from app.services.llm.http_provider import HttpLLMProvider


class GeminiProvider(HttpLLMProvider):
    name = "gemini"

    async def _request(
        self, client: httpx.AsyncClient, purpose: str, prompt: str
    ) -> httpx.Response:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        return await client.post(
            url,
            params={"key": self.api_key},
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
            },
            headers={"Content-Type": "application/json"},
        )

    def _response_text(self, payload: Mapping[str, Any]) -> str:
        candidates = payload.get("candidates", [])
        return str(candidates[0]["content"]["parts"][0]["text"])
