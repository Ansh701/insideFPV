from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CategoryWatch, Product, Retailer, TelegramUser, WatchlistItem
from app.services.seed import seed_database


async def test_seed_is_repeatable_and_creates_required_catalog(session: AsyncSession) -> None:
    first = await seed_database(session)
    second = await seed_database(session)

    assert first.products_created == 3
    assert first.watches_created == 3
    assert second.products_created == 0
    assert second.watches_created == 0
    assert await session.scalar(select(func.count()).select_from(Retailer)) == 4
    names = set((await session.scalars(select(Product.name))).all())
    assert {"Raspberry Pi 5", "Raspberry Pi 5-compatible HAT", "Holybro Pixhawk 6X"} <= names
    categories = set((await session.scalars(select(CategoryWatch.category))).all())
    assert categories == {"Flight Controllers", "Companion Computers"}
    assert await session.scalar(select(func.count()).select_from(TelegramUser)) == 1
    assert await session.scalar(select(func.count()).select_from(WatchlistItem)) == 3
