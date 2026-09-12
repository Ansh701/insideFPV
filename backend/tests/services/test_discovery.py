from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import CategoryWatch, Product
from app.services.discovery import DiscoveryService
from app.services.seed import seed_database
from app.sources.registry import default_registry


class DiscoveryFetcher:
    def __init__(self, *, fail_categories: bool = False) -> None:
        self.fail_categories = fail_categories

    async def get_text(self, url: str) -> str:
        if "category" in url or "collections" in url or "drone-parts" in url:
            if self.fail_categories:
                raise TimeoutError("category timed out")
            return (
                "<a href='/product/new-pixhawk-controller/?utm_source=category&ref=grid'>"
                "New Pixhawk Controller</a>"
                "<a href='/product/m3-random-frame-screws'>Random frame screws</a>"
            )
        return "<h1>Existing product</h1><p>Out of stock</p>"


async def test_category_discovery_inserts_new_searchable_product_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await seed_database(session)
        await session.execute(update(CategoryWatch).values(enabled=False))
        watch = await session.scalar(
            select(CategoryWatch).where(CategoryWatch.source_url.contains("product-category"))
        )
        assert watch is not None
        watch.enabled = True
        await session.commit()

    service = DiscoveryService(
        session_factory,
        registry=default_registry(),
        fetcher=DiscoveryFetcher(),
    )
    first = await service.run()
    second = await service.run()

    async with session_factory() as session:
        discovered = await session.scalar(
            select(Product).where(Product.canonical_url.contains("new-pixhawk-controller"))
        )
        assert first.products_discovered == 1
        assert second.products_discovered == 0
        assert discovered is not None
        assert discovered.canonical_url.endswith("/product/new-pixhawk-controller")
        assert discovered.category == "Flight Controllers"
        assert discovered.name == "New Pixhawk Controller"
        assert await session.scalar(select(func.count()).select_from(Product)) == 4


async def test_category_discovery_rejects_irrelevant_accessories(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await seed_database(session)
        await session.execute(update(CategoryWatch).values(enabled=False))
        watch = await session.scalar(
            select(CategoryWatch).where(CategoryWatch.source_url.contains("product-category"))
        )
        assert watch is not None
        watch.enabled = True
        await session.commit()

    await DiscoveryService(
        session_factory,
        registry=default_registry(),
        fetcher=DiscoveryFetcher(),
    ).run()

    async with session_factory() as session:
        irrelevant = await session.scalar(
            select(Product).where(Product.canonical_url.contains("random-frame-screws"))
        )
        assert irrelevant is None


async def test_category_discovery_failure_is_reported_without_deleting_products(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await seed_database(session)
        original_count = await session.scalar(select(func.count()).select_from(Product))

    result = await DiscoveryService(
        session_factory,
        registry=default_registry(),
        fetcher=DiscoveryFetcher(fail_categories=True),
    ).run()

    async with session_factory() as session:
        assert result.errors
        assert await session.scalar(select(func.count()).select_from(Product)) == original_count
