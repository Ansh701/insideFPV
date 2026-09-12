from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Alert, AlertDeliveryStatus, Product, ProductSnapshot, ProductStatus
from app.services.alerting import AlertDispatcher
from app.services.llm.service import LLMService
from app.services.monitor import MonitorService
from app.services.seed import seed_database
from app.sources.registry import default_registry

FIXTURES = Path(__file__).parents[1] / "fixtures"


class SequenceFetcher:
    def __init__(self, states: list[str], failures: set[str] | None = None) -> None:
        self.states = states
        self.failures = failures or set()
        self.calls: defaultdict[str, int] = defaultdict(int)

    async def get_text(self, url: str) -> str:
        if url in self.failures:
            raise TimeoutError("retailer timed out")
        index = min(self.calls[url], len(self.states) - 1)
        self.calls[url] += 1
        status = self.states[index]
        return (
            "<html><head><script type='application/ld+json'>"
            '{"@type":"Product","name":"Holybro Pixhawk 6X","offers":'
            f'{{"price":"25000","priceCurrency":"INR","availability":"https://schema.org/{status}"}}'
            "}</script></head><body></body></html>"
        )


class FailingMessaging:
    async def send_message(self, chat_id: int, text: str) -> str:
        from app.messaging.base import MessagingDeliveryError

        raise MessagingDeliveryError("simulated Telegram outage")


class RecordingMessaging:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> str:
        self.messages.append((chat_id, text))
        return "retry-message-id"


async def _pixhawk_id(session: AsyncSession) -> Any:
    return await session.scalar(select(Product.id).where(Product.name == "Holybro Pixhawk 6X"))


async def test_baseline_then_favorable_transition_creates_one_deduplicated_alert(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await seed_database(session)
        product_id = await _pixhawk_id(session)
    service = MonitorService(
        session_factory,
        registry=default_registry(),
        fetcher=SequenceFetcher(["OutOfStock", "InStock", "InStock"]),
        llm=LLMService([]),
        concurrency=2,
    )

    first = await service.run(product_ids=[product_id], trigger="test")
    second = await service.run(product_ids=[product_id], trigger="test")
    third = await service.run(product_ids=[product_id], trigger="test")

    async with session_factory() as session:
        assert first.alerts_created == 0
        assert second.alerts_created == 1
        assert third.alerts_created == 0
        assert await session.scalar(select(func.count()).select_from(ProductSnapshot)) == 3
        assert await session.scalar(select(func.count()).select_from(Alert)) == 1
        assert (
            await session.scalar(select(Product.current_status).where(Product.id == product_id))
            is ProductStatus.IN_STOCK
        )


async def test_one_retailer_failure_does_not_stop_other_products(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await seed_database(session)
        products = list((await session.scalars(select(Product).order_by(Product.name))).all())
        failed_url = products[0].canonical_url
        ids = [item.id for item in products[:2]]
    service = MonitorService(
        session_factory,
        registry=default_registry(),
        fetcher=SequenceFetcher(["InStock"], failures={failed_url}),
        llm=LLMService([]),
        concurrency=2,
    )

    result = await service.run(product_ids=ids, trigger="test")

    assert result.products_checked == 2
    assert result.errors_count == 1
    assert result.status == "COMPLETED_WITH_ERRORS"


async def test_telegram_failure_does_not_roll_back_observed_business_state(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await seed_database(session)
        product_id = await _pixhawk_id(session)
    dispatcher = AlertDispatcher(session_factory, FailingMessaging())
    service = MonitorService(
        session_factory,
        registry=default_registry(),
        fetcher=SequenceFetcher(["OutOfStock", "PreOrder"]),
        llm=LLMService([]),
        concurrency=1,
        dispatcher=dispatcher,
    )

    await service.run(product_ids=[product_id], trigger="test")
    result = await service.run(product_ids=[product_id], trigger="test")

    async with session_factory() as session:
        product = await session.get(Product, product_id)
        alert = await session.scalar(select(Alert))
        assert result.alerts_created == 1
        assert product is not None and product.current_status is ProductStatus.PREORDER
        assert alert is not None and alert.delivery_status is AlertDeliveryStatus.FAILED
        assert "simulated Telegram outage" in (alert.error or "")

    messaging = RecordingMessaging()
    retry = await AlertDispatcher(session_factory, messaging).retry_failed(limit=10)

    async with session_factory() as session:
        retried = await session.scalar(select(Alert))
        assert retry.attempted == 1
        assert retry.sent == 1
        assert retry.failed == 0
        assert len(messaging.messages) == 1
        assert retried is not None and retried.delivery_status is AlertDeliveryStatus.SENT
        assert retried.delivered_at is not None
