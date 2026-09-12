import re
import uuid
from decimal import Decimal
from typing import Protocol, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Product, ProductSnapshot, ProductStatus
from app.services.llm.schemas import ChatIntent, ChatIntentName
from app.services.search import ProductSearchItem, ProductSearchService, SearchFilters
from app.services.watchlist import (
    DuplicateWatchError,
    WatchlistService,
    WatchNotFoundError,
    WatchTargetError,
)


class IntentParser(Protocol):
    async def parse_chat_intent(self, message: str) -> ChatIntent: ...


class MonitorTrigger(Protocol):
    async def run(self, *, product_ids: list[uuid.UUID], trigger: str) -> "MonitorRunOutcome": ...


class MonitorRunOutcome(Protocol):
    products_checked: int
    errors_count: int


HELP_TEXT = (
    "I can search products, show current status/history, compare products, manage your watchlist, "
    "or check a product now. Try “show flight controllers in stock”, “watch Pixhawk 6X”, "
    "“show my watchlist”, or /help."
)


def _clean_target(value: str) -> str:
    return value.strip().strip("?.!")


def deterministic_intent(message: str) -> ChatIntent:
    raw = message.strip()
    lowered = raw.lower()
    command = re.match(
        r"^/(help|watchlist|watch|unwatch|status|history|check)(?:\s+(.+))?$", raw, re.I
    )
    if command:
        action, target = command.group(1).lower(), _clean_target(command.group(2) or "")
        mapping = {
            "help": ChatIntentName.HELP,
            "watchlist": ChatIntentName.LIST_WATCHLIST,
            "watch": ChatIntentName.ADD_WATCH,
            "unwatch": ChatIntentName.REMOVE_WATCH,
            "status": ChatIntentName.GET_STATUS,
            "history": ChatIntentName.GET_HISTORY,
            "check": ChatIntentName.CHECK_NOW,
        }
        return ChatIntent(
            intent=mapping[action],
            url=target if target.startswith(("http://", "https://")) else None,
            product_name=target or None,
        )
    if lowered in {"help", "what can you do?"}:
        return ChatIntent(intent=ChatIntentName.HELP)
    if re.search(r"\b(show|list)\s+(me\s+)?my\s+watchlist\b", lowered):
        return ChatIntent(intent=ChatIntentName.LIST_WATCHLIST)
    match = re.match(r"(?:stop watching|remove|unwatch)\s+(.+)", raw, re.I)
    if match:
        return ChatIntent(
            intent=ChatIntentName.REMOVE_WATCH, product_name=_clean_target(match.group(1))
        )
    match = re.match(r"(?:watch|track)\s+(.+)", raw, re.I)
    if match:
        target = _clean_target(match.group(1))
        return ChatIntent(
            intent=ChatIntentName.ADD_WATCH,
            url=target if target.startswith(("http://", "https://")) else None,
            product_name=None if target.startswith(("http://", "https://")) else target,
        )
    match = re.search(r"(?:check)\s+(.+?)\s+now\b", raw, re.I)
    if match:
        return ChatIntent(
            intent=ChatIntentName.CHECK_NOW, product_name=_clean_target(match.group(1))
        )
    match = re.search(
        r"(?:show (?:the )?history for|when was)\s+(.+?)(?:\s+last in stock)?[?.!]*$", raw, re.I
    )
    if match:
        return ChatIntent(
            intent=ChatIntentName.GET_HISTORY, product_name=_clean_target(match.group(1))
        )
    match = re.search(
        r"(?:is\s+(.+?)\s+available|status(?:\s+of|\s+for)?\s+(.+))[?.!]*$", raw, re.I
    )
    if match:
        return ChatIntent(
            intent=ChatIntentName.GET_STATUS,
            product_name=_clean_target(match.group(1) or match.group(2)),
        )
    if lowered.startswith(("find ", "show ")):
        category: str | None = None
        query: str | None = raw
        if "flight controller" in lowered or "pixhawk controller" in lowered:
            category = "Flight Controllers"
            query = None
        elif "companion computer" in lowered:
            category = "Companion Computers"
            query = None
        availability = (
            ProductStatus.IN_STOCK if "in stock" in lowered or "available" in lowered else None
        )
        price_match = re.search(r"under\s*(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)", lowered)
        max_price = Decimal(price_match.group(1).replace(",", "")) if price_match else None
        return ChatIntent(
            intent=ChatIntentName.SEARCH_PRODUCTS,
            query=query,
            category=category,
            availability=availability,
            max_price=max_price,
        )
    return ChatIntent(intent=ChatIntentName.UNKNOWN)


class ChatService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        llm: IntentParser,
        monitor: MonitorTrigger | None = None,
    ) -> None:
        self.session = session
        self.llm = llm
        self.monitor = monitor
        self.search = ProductSearchService()
        self.watchlist = WatchlistService()

    async def handle(self, telegram_user_id: int, message: str) -> str:
        intent = deterministic_intent(message)
        if intent.intent is ChatIntentName.UNKNOWN:
            intent = await self.llm.parse_chat_intent(message)
        try:
            return await self._execute(telegram_user_id, intent)
        except (WatchTargetError, DuplicateWatchError, WatchNotFoundError) as exc:
            return str(exc)

    async def _execute(self, user_id: int, intent: ChatIntent) -> str:
        if intent.intent in {ChatIntentName.UNKNOWN, ChatIntentName.HELP}:
            return HELP_TEXT
        if intent.intent is ChatIntentName.SEARCH_PRODUCTS:
            result = await self.search.search(
                self.session,
                SearchFilters(
                    query=intent.query,
                    category=intent.category,
                    availability=intent.availability,
                    min_price=intent.min_price,
                    max_price=intent.max_price,
                    retailer=intent.retailer,
                    limit=8,
                ),
            )
            if not result.items:
                suffix = f" Did you mean “{result.suggestion}”?" if result.suggestion else ""
                return f"No matching products are in the catalog.{suffix}"
            return "\n\n".join(self._format_product(item) for item in result.items)
        if intent.intent is ChatIntentName.GET_STATUS:
            product = await self._find_product(intent.product_name or intent.query)
            if product is None:
                return "I couldn't find that product. Try a more specific name."
            retailer = product.retailer.name
            price = (
                f"₹{product.current_price:,.2f}"
                if product.current_price is not None
                else "Not listed"
            )
            checked = (
                product.last_checked_at.isoformat()
                if product.last_checked_at
                else "Not checked yet"
            )
            return (
                f"{product.name}\nStatus: {product.current_status.value.replace('_', ' ')}\n"
                f"Price: {price}\nRetailer: {retailer}\nLast checked: {checked}\n"
                f"{product.canonical_url}"
            )
        if intent.intent is ChatIntentName.GET_HISTORY:
            product = await self._find_product(intent.product_name or intent.query)
            if product is None:
                return "I couldn't find that product. Try a more specific name."
            rows = list(
                (
                    await self.session.scalars(
                        select(ProductSnapshot)
                        .where(ProductSnapshot.product_id == product.id)
                        .order_by(ProductSnapshot.checked_at.desc())
                        .limit(10)
                    )
                ).all()
            )
            if not rows:
                return f"No monitoring history exists for {product.name} yet. Run a check first."
            return f"History for {product.name}:\n" + "\n".join(
                f"• {row.status.value.replace('_', ' ')} — {row.checked_at.isoformat()}"
                for row in rows
            )
        if intent.intent is ChatIntentName.ADD_WATCH:
            item = await self.watchlist.add(
                self.session,
                telegram_user_id=user_id,
                product_name=intent.product_name,
                url=intent.url,
            )
            return f"{item.product.name} was added to your watchlist."
        if intent.intent is ChatIntentName.REMOVE_WATCH:
            name = await self.watchlist.remove_by_name(
                self.session,
                telegram_user_id=user_id,
                product_name=intent.product_name or intent.query or "",
            )
            return f"Watch removed for {name}."
        if intent.intent is ChatIntentName.LIST_WATCHLIST:
            items = await self.watchlist.list(self.session, telegram_user_id=user_id)
            if not items:
                return (
                    "Your watchlist is empty. Track a product and I'll notify you after a "
                    "favorable change."
                )
            return "Your watchlist:\n" + "\n".join(
                f"• {item.product.name} — {item.product.current_status.value.replace('_', ' ')}"
                for item in items
            )
        if intent.intent is ChatIntentName.CHECK_NOW:
            if self.monitor is None:
                return "Fresh checking is unavailable right now. Your watch remains active."
            product = await self._find_product(intent.product_name or intent.query)
            if product is None:
                return "I couldn't find that product. Try a more specific name."
            monitor_result = await self.monitor.run(product_ids=[product.id], trigger="chat")
            checked_count = monitor_result.products_checked
            error_count = monitor_result.errors_count
            return f"Checked {checked_count} product. {error_count} check errors."
        if intent.intent is ChatIntentName.COMPARE_PRODUCTS:
            products = [await self._find_product(name) for name in intent.product_names[:2]]
            present = [item for item in products if item is not None]
            if len(present) < 2:
                return "Name two catalog products so I can compare stored price and availability."
            lines = []
            for product in present:
                price = (
                    f"₹{product.current_price:,.2f}"
                    if product.current_price is not None
                    else "price not listed"
                )
                lines.append(
                    f"• {product.name}: {product.current_status.value.replace('_', ' ')}, {price}"
                )
            return "Comparison:\n" + "\n".join(lines)
        return HELP_TEXT

    async def _find_product(self, query: str | None) -> Product | None:
        if not query:
            return None
        return cast(
            Product | None,
            await self.session.scalar(
                select(Product)
                .options(selectinload(Product.retailer))
                .where(func.lower(Product.name).like(f"%{query.strip().lower()}%"))
                .order_by(Product.name)
            ),
        )

    @staticmethod
    def _format_product(item: ProductSearchItem) -> str:
        name = item.name
        status = item.status.value.replace("_", " ")
        price_value = item.price
        price = f"₹{price_value:,.2f}" if price_value is not None else "Price not listed"
        retailer = item.retailer
        url = item.canonical_url
        return f"{name}\n{status} · {price} · {retailer}\n{url}"
