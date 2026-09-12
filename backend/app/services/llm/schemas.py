from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import ProductStatus
from app.sources.base import ProductExtraction


class ChatIntentName(StrEnum):
    SEARCH_PRODUCTS = "SEARCH_PRODUCTS"
    COMPARE_PRODUCTS = "COMPARE_PRODUCTS"
    GET_STATUS = "GET_STATUS"
    GET_HISTORY = "GET_HISTORY"
    ADD_WATCH = "ADD_WATCH"
    REMOVE_WATCH = "REMOVE_WATCH"
    LIST_WATCHLIST = "LIST_WATCHLIST"
    CHECK_NOW = "CHECK_NOW"
    HELP = "HELP"
    UNKNOWN = "UNKNOWN"


class ChatIntent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    intent: ChatIntentName
    query: str | None = None
    product_id: str | None = None
    product_name: str | None = None
    product_names: list[str] = Field(default_factory=list)
    url: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    availability: ProductStatus | None = None
    retailer: str | None = None
    category: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    provider: str | None = None


__all__ = ["ChatIntent", "ChatIntentName", "ProductExtraction"]
