import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import monotonic
from typing import cast

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.chat import router as chat_router
from app.api.dashboard import router as dashboard_router
from app.api.monitoring import router as monitoring_router
from app.api.products import router as products_router
from app.api.telegram import router as telegram_router
from app.api.watchlist import router as watchlist_router
from app.config import Settings, get_settings
from app.db import SessionFactory
from app.messaging.base import MessagingProvider
from app.messaging.telegram import TelegramMessagingProvider
from app.services.alerting import AlertDispatcher
from app.services.llm.factory import build_llm_service
from app.services.monitor import MonitorService
from app.sources.http import SafeHttpClient
from app.sources.registry import default_registry


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    telegram: object | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    factory = session_factory or SessionFactory
    registry = default_registry()
    llm = build_llm_service(app_settings)
    fetcher = SafeHttpClient(
        allowed_domains=registry.domains,
        timeout_seconds=app_settings.request_timeout,
        max_retries=app_settings.request_max_retries,
        user_agent=app_settings.user_agent,
    )
    telegram_provider = telegram or TelegramMessagingProvider(app_settings.telegram_bot_token)
    dispatcher = (
        AlertDispatcher(factory, cast(MessagingProvider, telegram_provider))
        if app_settings.telegram_bot_token
        else None
    )
    monitor = MonitorService(
        factory,
        registry=registry,
        fetcher=fetcher,
        llm=llm,
        concurrency=app_settings.monitor_concurrency,
        dispatcher=dispatcher,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await fetcher.close()

    production = app_settings.app_env == "production"
    app = FastAPI(
        title="RotorWatch API",
        version="0.1.0",
        debug=False,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = app_settings
    app.state.session_factory = factory
    app.state.telegram = telegram_provider
    app.state.llm = llm
    app.state.monitor = monitor
    app.state.alert_dispatcher = dispatcher
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=app_settings.allowed_hosts)
    if app_settings.allowed_cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.allowed_cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "X-Admin-Secret"],
        )

    rate_buckets: dict[str, deque[float]] = defaultdict(deque)

    @app.middleware("http")
    async def request_context(request: Request, call_next: object) -> object:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)
        protected = request.method in {"POST", "DELETE"} and request.url.path.startswith(
            ("/api/chat", "/api/watchlist", "/api/admin/", "/webhooks/telegram")
        )
        if protected:
            now = monotonic()
            host = request.client.host if request.client else "unknown"
            bucket = rate_buckets[f"{host}:{request.url.path}"]
            while bucket and now - bucket[0] >= 60:
                bucket.popleft()
            if len(bucket) >= app_settings.rate_limit_per_minute:
                structlog.contextvars.clear_contextvars()
                return JSONResponse(
                    status_code=429,
                    headers={"Retry-After": "60", "X-Request-ID": request_id},
                    content={
                        "error": {
                            "code": "RATE_LIMITED",
                            "message": "Too many requests reached this action.",
                            "action": "Wait up to one minute, then try again.",
                        }
                    },
                )
            bucket.append(now)
        try:
            response = await call_next(request)  # type: ignore[operator]
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
        structlog.get_logger().exception("unhandled_request_error", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "The request could not be completed.",
                    "action": (
                        "Try again shortly. If the problem continues, check the service logs."
                    ),
                }
            },
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready(request: Request) -> JSONResponse:
        try:
            async with request.app.state.session_factory() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "unavailable", "dependency": "database"},
            )
        return JSONResponse(content={"status": "ready"})

    app.include_router(products_router)
    app.include_router(watchlist_router)
    app.include_router(monitoring_router)
    app.include_router(dashboard_router)
    app.include_router(chat_router)
    app.include_router(telegram_router)
    return app


app = create_app()
