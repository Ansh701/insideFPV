from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

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
    app_base_url: str | None = None
    database_url: str = "postgresql+asyncpg://drone:drone@localhost:5432/drone_assistant"
    cors_origins: str | None = None
    trusted_hosts: str | None = None
    render_external_url: str | None = None
    render_external_hostname: str | None = None

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

    @model_validator(mode="after")
    def resolve_deployment_defaults(self) -> "Settings":
        if self.app_base_url:
            self.app_base_url = self.app_base_url.rstrip("/")
        elif self.render_external_url:
            self.app_base_url = self.render_external_url.rstrip("/")
        elif self.render_external_hostname:
            self.app_base_url = f"https://{self._hostname(self.render_external_hostname)}"
        else:
            self.app_base_url = "http://localhost:8000"
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
    def resolved_app_base_url(self) -> str:
        return self.app_base_url or "http://localhost:8000"

    @property
    def allowed_cors_origins(self) -> list[str]:
        if self.cors_origins:
            return self._split_csv(self.cors_origins)
        if self.app_env == "production":
            return []
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def allowed_hosts(self) -> list[str]:
        hosts = self._split_csv(self.trusted_hosts) if self.trusted_hosts else []
        if self.app_env != "production" and not hosts:
            hosts.extend(("localhost", "127.0.0.1", "testserver"))

        for candidate in (
            self.render_external_hostname,
            self.render_external_url,
            self.app_base_url,
        ):
            if candidate:
                hostname = self._hostname(candidate)
                if hostname and hostname not in hosts:
                    hosts.append(hostname)
        return hosts or ["localhost", "127.0.0.1"]

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _hostname(value: str) -> str:
        parsed = urlsplit(value if "://" in value else f"//{value}")
        return parsed.hostname or value.split(":", 1)[0]


@lru_cache
def get_settings() -> Settings:
    return Settings()
