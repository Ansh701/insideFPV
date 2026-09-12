from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_base_url: str = "http://localhost:8000"
    database_url: str = "postgresql+asyncpg://drone:drone@localhost:5432/drone_assistant"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    trusted_hosts: str = "localhost,127.0.0.1,testserver"

    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash-lite"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5"

    llm_provider_timeout_seconds: float = Field(default=8.0, gt=0, le=30)
    llm_max_retries: int = Field(default=1, ge=0, le=1)
    llm_provider_cooldown_seconds: int = Field(default=60, ge=0, le=3600)

    monitor_interval: str = "daily"
    monitor_concurrency: int = Field(default=5, ge=1, le=20)
    request_timeout: float = Field(default=12.0, gt=0, le=60)
    request_max_retries: int = Field(default=1, ge=0, le=2)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)
    user_agent: str = "RotorWatch/0.1 (+availability-monitor; contact=admin@example.invalid)"
    admin_secret: str = "development-only-change-me"
    demo_mode: bool = False

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env != "production":
            return self
        if self.admin_secret == "development-only-change-me" or len(self.admin_secret) < 24:
            raise ValueError(
                "ADMIN_SECRET must be a non-placeholder value of at least 24 characters."
            )
        if self.telegram_bot_token and not self.telegram_webhook_secret:
            raise ValueError(
                "TELEGRAM_WEBHOOK_SECRET is required when Telegram is enabled in production."
            )
        return self

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def configured_llm_providers(self) -> tuple[str, ...]:
        configured: list[str] = []
        if self.gemini_api_key:
            configured.append("gemini")
        if self.openai_api_key:
            configured.append("openai")
        if self.anthropic_api_key:
            configured.append("anthropic")
        return tuple(configured)

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def allowed_hosts(self) -> list[str]:
        return [item.strip() for item in self.trusted_hosts.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
