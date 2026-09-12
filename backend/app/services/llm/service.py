import asyncio
import time
from collections.abc import Sequence
from typing import TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from app.models import ProductStatus
from app.services.llm.base import LLMProvider, ProviderFailure
from app.services.llm.schemas import ChatIntent, ChatIntentName, ProductExtraction

logger = structlog.get_logger()
SchemaT = TypeVar("SchemaT", bound=BaseModel)


PRODUCT_PROMPT = """Classify the product evidence. Return JSON with exactly these fields:
status (IN_STOCK, OUT_OF_STOCK, PREORDER, UNKNOWN), product_name, price, currency,
manufacturer, category, attributes, compatibility, confidence (0..1), evidence (short quoted cues).
Never infer availability from general product knowledge. Evidence:\n{content}"""

CHAT_PROMPT = """Convert the message into one structured action. Supported intent values:
SEARCH_PRODUCTS, COMPARE_PRODUCTS, GET_STATUS, GET_HISTORY, ADD_WATCH, REMOVE_WATCH,
LIST_WATCHLIST, CHECK_NOW, HELP, UNKNOWN. Return JSON with intent plus only relevant fields from:
query, product_id, product_name, product_names, url, min_price, max_price, availability,
retailer, category, attributes. Message:\n{message}"""


class LLMService:
    def __init__(
        self,
        providers: Sequence[LLMProvider],
        *,
        timeout_seconds: float = 8,
        max_retries: int = 1,
        repair_invalid: bool = True,
        cooldown_seconds: int = 60,
    ) -> None:
        self.providers = list(providers)
        self.timeout_seconds = timeout_seconds
        self.max_retries = min(max_retries, 1)
        self.repair_invalid = repair_invalid
        self.cooldown_seconds = cooldown_seconds
        self._cooldowns: dict[str, float] = {}

    async def classify_product(self, content: str) -> ProductExtraction:
        result = await self._run(
            purpose="product_classification",
            prompt=PRODUCT_PROMPT.format(content=content[:12000]),
            schema=ProductExtraction,
        )
        if result is None:
            return ProductExtraction(
                status=ProductStatus.UNKNOWN,
                confidence=0,
                classification_source="FALLBACK",
                evidence=["All configured LLM providers were unavailable or invalid."],
            )
        typed = ProductExtraction.model_validate(result.model_dump())
        typed.classification_source = "LLM"
        return typed

    async def parse_chat_intent(self, message: str) -> ChatIntent:
        result = await self._run(
            purpose="chat_intent",
            prompt=CHAT_PROMPT.format(message=message[:2000]),
            schema=ChatIntent,
        )
        if result is None:
            return ChatIntent(intent=ChatIntentName.UNKNOWN)
        return ChatIntent.model_validate(result.model_dump())

    async def _run(self, *, purpose: str, prompt: str, schema: type[SchemaT]) -> SchemaT | None:
        fallback_used = False
        for provider in self.providers:
            if (
                not provider.is_configured
                or self._cooldowns.get(provider.name, 0) > time.monotonic()
            ):
                continue
            retry_count = 0
            repair_used = False
            while True:
                started = time.monotonic()
                try:
                    payload = await asyncio.wait_for(
                        provider.generate_json(purpose, prompt), timeout=self.timeout_seconds
                    )
                    result = schema.model_validate(payload)
                    if hasattr(result, "provider"):
                        result.provider = provider.name
                    logger.info(
                        "llm_call",
                        purpose=purpose,
                        provider=provider.name,
                        model=provider.model,
                        result="success",
                        fallback_used=fallback_used,
                        duration_ms=round((time.monotonic() - started) * 1000),
                    )
                    return result
                except ValidationError as exc:
                    if self.repair_invalid and not repair_used:
                        repair_used = True
                        prompt = (
                            f"{prompt}\nThe prior output failed validation. "
                            "Return only valid JSON. "
                            f"Validation summary: {str(exc)[:300]}"
                        )
                        continue
                    logger.warning(
                        "llm_call",
                        purpose=purpose,
                        provider=provider.name,
                        result="invalid_output",
                    )
                    break
                except TimeoutError:
                    failure = ProviderFailure(
                        "Provider timed out.", retryable=True, category="TIMEOUT"
                    )
                except ProviderFailure as exc:
                    failure = exc
                except Exception:
                    raise
                logger.warning(
                    "llm_call",
                    purpose=purpose,
                    provider=provider.name,
                    model=provider.model,
                    result="failure",
                    failure_category=failure.category,
                    fallback_used=fallback_used,
                )
                if failure.retryable and retry_count < self.max_retries:
                    await asyncio.sleep(0.1 * (2**retry_count))
                    retry_count += 1
                    continue
                if failure.retryable and self.cooldown_seconds:
                    self._cooldowns[provider.name] = time.monotonic() + self.cooldown_seconds
                break
            fallback_used = True
        return None
