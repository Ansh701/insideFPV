import asyncio
from urllib.parse import urljoin, urlsplit

import httpx

from app.services.url_security import normalize_supported_url, validate_public_resolution


class RetailerFetchError(RuntimeError):
    pass


class SafeHttpClient:
    def __init__(
        self,
        *,
        allowed_domains: set[str],
        timeout_seconds: float,
        max_retries: int,
        user_agent: str,
        max_response_bytes: int = 2_000_000,
    ) -> None:
        self.allowed_domains = allowed_domains
        self.max_retries = max_retries
        self.max_response_bytes = max_response_bytes
        self.client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"},
            follow_redirects=False,
        )

    async def get_text(self, url: str) -> str:
        current = normalize_supported_url(url, self.allowed_domains)
        for _redirect_count in range(4):
            parsed = urlsplit(current)
            await validate_public_resolution(
                parsed.hostname or "", parsed.port or (443 if parsed.scheme == "https" else 80)
            )
            response = await self._request_with_retry(current)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise RetailerFetchError("Retailer returned an invalid redirect.")
                current = normalize_supported_url(urljoin(current, location), self.allowed_domains)
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RetailerFetchError(
                    f"Retailer responded with HTTP {response.status_code}."
                ) from exc
            content_length = int(response.headers.get("content-length", 0) or 0)
            if (
                content_length > self.max_response_bytes
                or len(response.content) > self.max_response_bytes
            ):
                raise RetailerFetchError("Retailer response exceeded the safe size limit.")
            return response.text
        raise RetailerFetchError("Retailer redirected too many times.")

    async def _request_with_retry(self, url: str) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.get(url)
                if (
                    response.status_code == 429 or response.status_code >= 500
                ) and attempt < self.max_retries:
                    retry_after = response.headers.get("retry-after")
                    delay = min(float(retry_after), 2) if retry_after else 0.2 * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= self.max_retries:
                    raise RetailerFetchError(
                        "Retailer did not respond before the request timed out."
                    ) from exc
                await asyncio.sleep(0.2 * (2**attempt))
        raise RetailerFetchError("Retailer request failed.")

    async def close(self) -> None:
        await self.client.aclose()
