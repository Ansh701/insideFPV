import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Product, Retailer, TelegramUser, WatchlistItem
from app.services.url_security import UnsafeUrlError, normalize_supported_url
from app.sources.registry import AdapterRegistry, default_registry


class WatchTargetError(ValueError):
    pass


class DuplicateWatchError(ValueError):
    pass


class WatchNotFoundError(ValueError):
    pass


class WatchlistService:
    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self.registry = registry or default_registry()

    async def ensure_user(
        self,
        session: AsyncSession,
        telegram_user_id: int,
        *,
        chat_id: int | None = None,
        username: str | None = None,
        first_name: str | None = None,
    ) -> TelegramUser:
        user = await session.scalar(
            select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_user_id)
        )
        if user is None:
            user = TelegramUser(
                telegram_user_id=telegram_user_id,
                chat_id=chat_id if chat_id is not None else telegram_user_id,
                username=username,
                first_name=first_name,
            )
            session.add(user)
            await session.flush()
        else:
            if chat_id is not None:
                user.chat_id = chat_id
            user.username = username or user.username
            user.first_name = first_name or user.first_name
        return user

    async def add(
        self,
        session: AsyncSession,
        *,
        telegram_user_id: int,
        product_name: str | None = None,
        url: str | None = None,
    ) -> WatchlistItem:
        if bool(product_name) == bool(url):
            raise WatchTargetError("Provide exactly one product name or supported retailer URL.")
        user = await self.ensure_user(session, telegram_user_id)
        if url:
            try:
                canonical = normalize_supported_url(url, self.registry.domains)
            except UnsafeUrlError as exc:
                raise WatchTargetError(str(exc)) from exc
            adapter = self.registry.resolve(canonical)
            product = await session.scalar(
                select(Product).where(Product.canonical_url == canonical)
            )
            if product is None:
                retailer = await session.scalar(
                    select(Retailer).where(Retailer.domain == adapter.domain)
                )
                if retailer is None:
                    raise WatchTargetError("The supported retailer has not been seeded yet.")
                slug = canonical.rstrip("/").rsplit("/", 1)[-1]
                display_name = re.sub(r"[-_]+", " ", slug).title()
                product = Product(
                    retailer_id=retailer.id,
                    canonical_url=canonical,
                    name=display_name,
                    normalized_name=display_name.lower(),
                    category="Other",
                )
                session.add(product)
                await session.flush()
        else:
            assert product_name is not None
            product = await session.scalar(
                select(Product)
                .where(func.lower(Product.name).like(f"%{product_name.strip().lower()}%"))
                .order_by(Product.name)
            )
            if product is None:
                raise WatchTargetError(f'No known product matches "{product_name}".')
        existing = await session.scalar(
            select(WatchlistItem).where(
                WatchlistItem.telegram_user_id == user.id,
                WatchlistItem.product_id == product.id,
            )
        )
        if existing and existing.enabled:
            raise DuplicateWatchError(f'"{product.name}" is already on this watchlist.')
        if existing:
            existing.enabled = True
            item = existing
        else:
            item = WatchlistItem(telegram_user_id=user.id, product_id=product.id, enabled=True)
            session.add(item)
        # Avoid async lazy-loading after commit in API and chat response formatting.
        item.product = product
        await session.commit()
        return item

    async def list(self, session: AsyncSession, *, telegram_user_id: int) -> list[WatchlistItem]:
        statement = (
            select(WatchlistItem)
            .join(TelegramUser)
            .options(selectinload(WatchlistItem.product).selectinload(Product.retailer))
            .where(
                TelegramUser.telegram_user_id == telegram_user_id,
                WatchlistItem.enabled.is_(True),
            )
            .order_by(WatchlistItem.created_at)
        )
        return list((await session.scalars(statement)).all())

    async def remove(
        self, session: AsyncSession, *, telegram_user_id: int, watch_id: uuid.UUID
    ) -> None:
        item = await session.scalar(
            select(WatchlistItem)
            .join(TelegramUser)
            .where(
                WatchlistItem.id == watch_id,
                TelegramUser.telegram_user_id == telegram_user_id,
                WatchlistItem.enabled.is_(True),
            )
        )
        if item is None:
            raise WatchNotFoundError("The active watch was not found.")
        item.enabled = False
        await session.commit()

    async def remove_by_name(
        self, session: AsyncSession, *, telegram_user_id: int, product_name: str
    ) -> str:
        item = await session.scalar(
            select(WatchlistItem)
            .join(TelegramUser)
            .join(Product)
            .where(
                TelegramUser.telegram_user_id == telegram_user_id,
                WatchlistItem.enabled.is_(True),
                func.lower(Product.name).like(f"%{product_name.strip().lower()}%"),
            )
            .options(selectinload(WatchlistItem.product))
        )
        if item is None:
            raise WatchNotFoundError(f'No active watch matches "{product_name}".')
        name = item.product.name
        item.enabled = False
        await session.commit()
        return name
