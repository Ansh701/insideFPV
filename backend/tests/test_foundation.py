from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import UniqueConstraint

from app.config import Settings
from app.models import Base, ProductStatus


def test_settings_normalize_postgres_driver_and_provider_priority() -> None:
    settings = Settings(
        database_url="postgres://user:pass@db.example/rotorwatch",
        gemini_api_key="gem-key",
        openai_api_key="open-key",
        anthropic_api_key="anth-key",
    )

    assert settings.database_url == "postgresql+asyncpg://user:pass@db.example/rotorwatch"
    assert settings.configured_llm_providers == ("gemini", "openai", "anthropic")


def test_development_cors_accepts_both_local_vite_hostnames() -> None:
    settings = Settings()

    assert set(settings.allowed_cors_origins) == {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }


def test_production_render_url_host_and_same_origin_cors_defaults() -> None:
    settings = Settings(
        app_env="production",
        admin_secret="a-real-random-deployment-secret",
        render_external_url="https://rotorwatch.onrender.com",
        render_external_hostname="rotorwatch.onrender.com",
    )

    assert settings.app_base_url == "https://rotorwatch.onrender.com"
    assert settings.resolved_app_base_url == settings.app_base_url
    assert settings.allowed_cors_origins == []
    assert "rotorwatch.onrender.com" in settings.allowed_hosts


def test_explicit_base_url_and_trusted_hosts_override_render_defaults() -> None:
    settings = Settings(
        app_env="production",
        admin_secret="a-real-random-deployment-secret",
        app_base_url="https://drones.example.in/",
        trusted_hosts="drones.example.in",
        render_external_url="https://rotorwatch.onrender.com",
        render_external_hostname="rotorwatch.onrender.com",
    )

    assert settings.resolved_app_base_url == "https://drones.example.in"
    assert settings.allowed_hosts == ["drones.example.in", "rotorwatch.onrender.com"]


def test_product_status_is_one_normalized_enum() -> None:
    assert {status.value for status in ProductStatus} == {
        "IN_STOCK",
        "OUT_OF_STOCK",
        "PREORDER",
        "UNKNOWN",
    }


def test_production_rejects_placeholder_admin_secret() -> None:
    with pytest.raises(ValidationError, match="ADMIN_SECRET"):
        Settings(app_env="production")


def test_production_telegram_requires_webhook_secret() -> None:
    with pytest.raises(ValidationError, match="TELEGRAM_WEBHOOK_SECRET"):
        Settings(
            app_env="production",
            admin_secret="a-real-random-deployment-secret",
            telegram_bot_token="bot-token",
        )


def test_schema_contains_compact_core_tables_and_idempotency_constraints() -> None:
    expected = {
        "retailers",
        "products",
        "product_snapshots",
        "watchlist_items",
        "category_watches",
        "alerts",
        "monitor_runs",
        "telegram_users",
        "processed_telegram_updates",
    }
    assert expected == set(Base.metadata.tables)

    watch_constraints = Base.metadata.tables["watchlist_items"].constraints
    assert any(
        isinstance(item, UniqueConstraint)
        and {column.name for column in item.columns} == {"telegram_user_id", "product_id"}
        for item in watch_constraints
    )
    assert Base.metadata.tables["products"].c.current_price.type.python_type is Decimal
