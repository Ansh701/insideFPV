from collections.abc import AsyncIterator

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db import get_session
from app.main import create_app
from app.models import ProcessedTelegramUpdate
from app.services.seed import seed_database


class TelegramStub:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> str:
        self.messages.append((chat_id, text))
        return "1"

    def parse_incoming(self, update: dict[str, object]) -> object:
        from app.messaging.telegram import TelegramIncoming

        message = update["message"]
        assert isinstance(message, dict)
        sender = message["from"]
        chat = message["chat"]
        assert isinstance(sender, dict) and isinstance(chat, dict)
        return TelegramIncoming(
            update_id=int(update["update_id"]),
            telegram_user_id=int(sender["id"]),
            chat_id=int(chat["id"]),
            text=str(message["text"]),
            username=str(sender.get("username") or "") or None,
            first_name=str(sender.get("first_name") or "") or None,
        )


async def test_health_products_admin_security_and_duplicate_webhook(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await seed_database(session)

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    telegram = TelegramStub()
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite://",
        admin_secret="correct-secret",
        telegram_bot_token="test-token",
        telegram_webhook_secret="webhook-secret",
    )
    app = create_app(settings=settings, session_factory=session_factory, telegram=telegram)
    app.dependency_overrides[get_session] = session_override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        assert (await client.get("/health")).json() == {"status": "ok"}
        products = await client.get("/api/products")
        assert products.status_code == 200
        assert products.json()["total"] == 3
        assert (await client.post("/api/admin/monitor/run")).status_code == 401
        retry = await client.post(
            "/api/admin/alerts/retry", headers={"X-Admin-Secret": "correct-secret"}
        )
        assert retry.status_code == 200
        assert retry.json() == {"attempted": 0, "sent": 0, "failed": 0}

        update = {
            "update_id": 9001,
            "message": {
                "text": "/help",
                "chat": {"id": 123},
                "from": {"id": 456, "username": "pilot", "first_name": "Asha"},
            },
        }
        headers = {"X-Telegram-Bot-Api-Secret-Token": "webhook-secret"}
        first = await client.post("/webhooks/telegram", json=update, headers=headers)
        duplicate = await client.post("/webhooks/telegram", json=update, headers=headers)
        rejected = await client.post("/webhooks/telegram", json=update)

    assert first.json()["status"] == "processed"
    assert duplicate.json()["status"] == "duplicate"
    assert rejected.status_code == 401
    assert len(telegram.messages) == 1
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ProcessedTelegramUpdate)) == 1


async def test_api_error_response_explains_unsupported_watch_url(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await seed_database(session)

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    settings = Settings(app_env="test", database_url="sqlite+aiosqlite://")
    app = create_app(settings=settings, session_factory=session_factory)
    app.dependency_overrides[get_session] = session_override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/watchlist", json={"telegram_user_id": 0, "url": "http://127.0.0.1/private"}
        )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "INVALID_WATCH_TARGET"
    assert "supported retailer" in body["error"]["action"].lower()


async def test_state_changing_endpoints_have_a_bounded_process_local_rate_limit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await seed_database(session)

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite://",
        rate_limit_per_minute=2,
    )
    app = create_app(settings=settings, session_factory=session_factory)
    app.dependency_overrides[get_session] = session_override
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        first = await client.post("/api/chat", json={"telegram_user_id": 0, "message": "/help"})
        second = await client.post("/api/chat", json={"telegram_user_id": 0, "message": "/help"})
        limited = await client.post("/api/chat", json={"telegram_user_id": 0, "message": "/help"})
        retry_first = await client.post("/api/admin/alerts/retry")
        retry_second = await client.post("/api/admin/alerts/retry")
        retry_limited = await client.post("/api/admin/alerts/retry")

    assert first.status_code == 200
    assert second.status_code == 200
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "60"
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert retry_first.status_code == 401
    assert retry_second.status_code == 401
    assert retry_limited.status_code == 429
