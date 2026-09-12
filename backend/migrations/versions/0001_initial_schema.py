"""Create the RotorWatch core schema.

Revision ID: 0001
Revises: None
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

uuid_type = sa.Uuid()
json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
product_status = sa.Enum(
    "IN_STOCK", "OUT_OF_STOCK", "PREORDER", "UNKNOWN", name="product_status", native_enum=False
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "retailers",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column("domain", sa.String(255), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "telegram_users",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255)),
        sa.Column("first_name", sa.String(255)),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "monitor_runs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("products_checked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_changed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("alerts_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text()),
        sa.Column("trigger", sa.String(32), nullable=False, server_default="scheduled"),
    )
    op.create_table(
        "products",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "retailer_id",
            uuid_type,
            sa.ForeignKey("retailers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_identifier", sa.String(255)),
        sa.Column("canonical_url", sa.String(2048), nullable=False, unique=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("normalized_name", sa.String(500), nullable=False),
        sa.Column("manufacturer", sa.String(255)),
        sa.Column("category", sa.String(120), nullable=False, server_default="Other"),
        sa.Column("current_status", product_status, nullable=False, server_default="UNKNOWN"),
        sa.Column("current_price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("attributes", json_type, nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "retailer_id", "external_identifier", name="uq_product_retailer_external"
        ),
    )
    op.create_index("ix_products_normalized_name", "products", ["normalized_name"])
    op.create_table(
        "product_snapshots",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "product_id",
            uuid_type,
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", product_status, nullable=False),
        sa.Column("price", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("attributes", json_type, nullable=False),
        sa.Column("classification_source", sa.String(32), nullable=False),
        sa.Column("classification_provider", sa.String(32)),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error", sa.Text()),
    )
    op.create_index(
        "ix_snapshots_product_checked", "product_snapshots", ["product_id", "checked_at"]
    )
    op.create_table(
        "watchlist_items",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "telegram_user_id",
            uuid_type,
            sa.ForeignKey("telegram_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            uuid_type,
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("telegram_user_id", "product_id", name="uq_watch_user_product"),
    )
    op.create_table(
        "category_watches",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "retailer_id",
            uuid_type,
            sa.ForeignKey("retailers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("query", sa.String(255), nullable=False, server_default=""),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True)),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("retailer_id", "category", "query", name="uq_category_watch"),
    )
    op.create_table(
        "alerts",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "user_id",
            uuid_type,
            sa.ForeignKey("telegram_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            uuid_type,
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            uuid_type,
            sa.ForeignKey("product_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("delivery_status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("event_fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
    )
    op.create_table(
        "processed_telegram_updates",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("update_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("processed_telegram_updates")
    op.drop_table("alerts")
    op.drop_table("category_watches")
    op.drop_table("watchlist_items")
    op.drop_index("ix_snapshots_product_checked", table_name="product_snapshots")
    op.drop_table("product_snapshots")
    op.drop_index("ix_products_normalized_name", table_name="products")
    op.drop_table("products")
    op.drop_table("monitor_runs")
    op.drop_table("telegram_users")
    op.drop_table("retailers")
