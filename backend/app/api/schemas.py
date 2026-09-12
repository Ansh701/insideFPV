import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import ProductStatus


class WatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telegram_user_id: int = 0
    product_name: str | None = Field(default=None, min_length=2, max_length=500)
    url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def one_target(self) -> "WatchCreate":
        if bool(self.product_name) == bool(self.url):
            raise ValueError("Provide exactly one product_name or url.")
        return self


class WatchResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    retailer: str
    status: ProductStatus
    price: Decimal | None
    canonical_url: str
    enabled: bool
    created_at: datetime


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telegram_user_id: int = 0
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    response: str


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")

    update_id: int
    message: dict[str, Any] | None = None
    edited_message: dict[str, Any] | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    action: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
