import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class ProductStatus(StrEnum):
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    PREORDER = "PREORDER"
    UNKNOWN = "UNKNOWN"


class MonitorRunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class AlertEventType(StrEnum):
    BACK_IN_STOCK = "BACK_IN_STOCK"
    PREORDER_OPENED = "PREORDER_OPENED"


class AlertDeliveryStatus(StrEnum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Base(DeclarativeBase):
    pass


json_type = JSON().with_variant(JSONB(), "postgresql")
status_enum = Enum(ProductStatus, name="product_status", native_enum=False, length=20)


class Retailer(Base):
    __tablename__ = "retailers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    domain: Mapped[str] = mapped_column(String(255), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    products: Mapped[list["Product"]] = relationship(back_populates="retailer")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("retailer_id", "external_identifier", name="uq_product_retailer_external"),
        Index("ix_products_normalized_name", "normalized_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    retailer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("retailers.id", ondelete="CASCADE"))
    external_identifier: Mapped[str | None] = mapped_column(String(255))
    canonical_url: Mapped[str] = mapped_column(String(2048), unique=True)
    name: Mapped[str] = mapped_column(String(500))
    normalized_name: Mapped[str] = mapped_column(String(500))
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(120), default="Other")
    current_status: Mapped[ProductStatus] = mapped_column(
        status_enum, default=ProductStatus.UNKNOWN
    )
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    attributes: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    retailer: Mapped[Retailer] = relationship(back_populates="products")
    snapshots: Mapped[list["ProductSnapshot"]] = relationship(back_populates="product")
    watches: Mapped[list["WatchlistItem"]] = relationship(back_populates="product")


class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"
    __table_args__ = (Index("ix_snapshots_product_checked", "product_id", "checked_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    status: Mapped[ProductStatus] = mapped_column(status_enum)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    attributes: Mapped[dict[str, Any]] = mapped_column(json_type, default=dict)
    classification_source: Mapped[str] = mapped_column(String(32))
    classification_provider: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    content_hash: Mapped[str] = mapped_column(String(64))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    error: Mapped[str | None] = mapped_column(Text)

    product: Mapped[Product] = relationship(back_populates="snapshots")


class TelegramUser(Base):
    __tablename__ = "telegram_users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    watches: Mapped[list["WatchlistItem"]] = relationship(back_populates="telegram_user")


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("telegram_user_id", "product_id", name="uq_watch_user_product"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    telegram_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("telegram_users.id", ondelete="CASCADE")
    )
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    telegram_user: Mapped[TelegramUser] = relationship(back_populates="watches")
    product: Mapped[Product] = relationship(back_populates="watches")


class CategoryWatch(Base):
    __tablename__ = "category_watches"
    __table_args__ = (
        UniqueConstraint("retailer_id", "category", "query", name="uq_category_watch"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    retailer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("retailers.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(120))
    query: Mapped[str] = mapped_column(String(255), default="")
    source_url: Mapped[str | None] = mapped_column(String(2048))
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    retailer: Mapped[Retailer] = relationship()


class MonitorRun(Base):
    __tablename__ = "monitor_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[MonitorRunStatus] = mapped_column(
        Enum(MonitorRunStatus, native_enum=False, length=32), default=MonitorRunStatus.RUNNING
    )
    products_checked: Mapped[int] = mapped_column(default=0)
    products_changed: Mapped[int] = mapped_column(default=0)
    alerts_created: Mapped[int] = mapped_column(default=0)
    errors_count: Mapped[int] = mapped_column(default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(String(32), default="scheduled")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("telegram_users.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_snapshots.id", ondelete="CASCADE")
    )
    event_type: Mapped[AlertEventType] = mapped_column(
        Enum(AlertEventType, native_enum=False, length=32)
    )
    delivery_status: Mapped[AlertDeliveryStatus] = mapped_column(
        Enum(AlertDeliveryStatus, native_enum=False, length=16),
        default=AlertDeliveryStatus.PENDING,
    )
    event_fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class ProcessedTelegramUpdate(Base):
    __tablename__ = "processed_telegram_updates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    update_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
