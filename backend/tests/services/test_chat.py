from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, ProductSnapshot, ProductStatus, utcnow
from app.services.chat import ChatService
from app.services.llm.schemas import ChatIntent, ChatIntentName
from app.services.seed import seed_database


class IntentLLM:
    def __init__(self, intent: ChatIntent | None = None) -> None:
        self.intent = intent or ChatIntent(intent=ChatIntentName.UNKNOWN)

    async def parse_chat_intent(self, message: str) -> ChatIntent:
        return self.intent


class MonitorSpy:
    def __init__(self) -> None:
        self.product_ids: list[object] = []

    async def run(self, *, product_ids: list[object], trigger: str) -> object:
        self.product_ids.extend(product_ids)
        return type("Result", (), {"products_checked": len(product_ids), "errors_count": 0})()


async def _prepare(session: AsyncSession) -> Product:
    await seed_database(session)
    raspberry_pi = await session.scalar(select(Product).where(Product.name == "Raspberry Pi 5"))
    assert raspberry_pi is not None
    raspberry_pi.current_status = ProductStatus.IN_STOCK
    raspberry_pi.current_price = 8189
    raspberry_pi.last_checked_at = utcnow()
    product = await session.scalar(select(Product).where(Product.name == "Holybro Pixhawk 6X"))
    assert product is not None
    product.current_status = ProductStatus.IN_STOCK
    product.current_price = 25000
    product.last_checked_at = utcnow()
    session.add(
        ProductSnapshot(
            product_id=product.id,
            status=ProductStatus.OUT_OF_STOCK,
            price=25000,
            currency="INR",
            classification_source="DETERMINISTIC",
            content_hash="a" * 64,
        )
    )
    await session.commit()
    return product


async def test_deterministic_search_status_history_and_watchlist_commands(
    session: AsyncSession,
) -> None:
    await _prepare(session)
    service = ChatService(session, llm=IntentLLM())

    search = await service.handle(0, "show flight controllers in stock")
    filtered = await service.handle(0, "show companion computers under 15000")
    status = await service.handle(0, "is Pixhawk 6X available?")
    history = await service.handle(0, "show history for Pixhawk 6X")
    await service.handle(0, "stop watching Pixhawk 6X")
    watched = await service.handle(0, "watch Pixhawk 6X")
    listed = await service.handle(0, "show my watchlist")
    removed = await service.handle(0, "stop watching Pixhawk 6X")

    assert "Holybro Pixhawk 6X" in search
    assert "Raspberry Pi 5" in filtered
    assert "IN STOCK" in status and "Zbotic" in status and "https://" in status
    assert "OUT OF STOCK" in history
    assert "added" in watched.lower()
    assert "Holybro Pixhawk 6X" in listed
    assert "removed" in removed.lower()


async def test_check_now_uses_shared_monitor_service(session: AsyncSession) -> None:
    product = await _prepare(session)
    monitor = MonitorSpy()
    service = ChatService(session, llm=IntentLLM(), monitor=monitor)

    response = await service.handle(0, "check Pixhawk 6X now")

    assert monitor.product_ids == [product.id]
    assert "checked 1" in response.lower()


async def test_mock_llm_intents_execute_application_logic(session: AsyncSession) -> None:
    await _prepare(session)
    intent = ChatIntent(
        intent=ChatIntentName.SEARCH_PRODUCTS,
        query="Pixhawk",
        availability=ProductStatus.IN_STOCK,
    )

    response = await ChatService(session, llm=IntentLLM(intent)).handle(
        0, "please find the right one"
    )

    assert "Holybro Pixhawk 6X" in response


async def test_unknown_intent_and_no_llm_have_helpful_fallback(session: AsyncSession) -> None:
    await _prepare(session)
    response = await ChatService(session, llm=IntentLLM()).handle(0, "tell me a joke")
    assert "I can search" in response


async def test_compare_intent_uses_stored_facts(session: AsyncSession) -> None:
    await _prepare(session)
    intent = ChatIntent(
        intent=ChatIntentName.COMPARE_PRODUCTS,
        product_names=["Raspberry Pi 5", "Holybro Pixhawk 6X"],
    )
    response = await ChatService(session, llm=IntentLLM(intent)).handle(0, "compare them")
    assert "Raspberry Pi 5" in response and "Holybro Pixhawk 6X" in response
