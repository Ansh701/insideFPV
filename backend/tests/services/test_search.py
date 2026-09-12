from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, ProductStatus, Retailer
from app.services.search import ProductSearchService, SearchFilters


async def _catalog(session: AsyncSession) -> None:
    robu = Retailer(name="Robu", domain="robu.in")
    zbotic = Retailer(name="Zbotic", domain="zbotic.in")
    session.add_all([robu, zbotic])
    await session.flush()
    session.add_all(
        [
            Product(
                retailer_id=robu.id,
                canonical_url="https://robu.in/product/pi-5",
                name="Raspberry Pi 5 8GB",
                normalized_name="raspberry pi 5 8gb",
                category="Companion Computers",
                current_status=ProductStatus.IN_STOCK,
                current_price=Decimal("14999"),
                manufacturer="Raspberry Pi",
            ),
            Product(
                retailer_id=zbotic.id,
                canonical_url="https://zbotic.in/product/pixhawk-6x",
                name="Holybro Pixhawk 6X",
                normalized_name="holybro pixhawk 6x",
                category="Flight Controllers",
                current_status=ProductStatus.IN_STOCK,
                current_price=Decimal("25000"),
                manufacturer="Holybro",
            ),
            Product(
                retailer_id=robu.id,
                canonical_url="https://robu.in/product/pixhawk-6c",
                name="Pixhawk 6C Mini",
                normalized_name="pixhawk 6c mini",
                category="Flight Controllers",
                current_status=ProductStatus.OUT_OF_STOCK,
                current_price=Decimal("12999"),
                manufacturer="Holybro",
            ),
        ]
    )
    await session.commit()


async def test_search_supports_name_and_all_structured_filters(session: AsyncSession) -> None:
    await _catalog(session)
    service = ProductSearchService()

    assert (await service.search(session, SearchFilters(query="Raspberry"))).items[
        0
    ].name == "Raspberry Pi 5 8GB"
    assert (
        len((await service.search(session, SearchFilters(category="Flight Controllers"))).items)
        == 2
    )
    assert (
        len(
            (
                await service.search(session, SearchFilters(availability=ProductStatus.IN_STOCK))
            ).items
        )
        == 2
    )
    assert (
        len((await service.search(session, SearchFilters(max_price=Decimal("15000")))).items) == 2
    )
    assert len((await service.search(session, SearchFilters(retailer="Zbotic"))).items) == 1

    combined = await service.search(
        session,
        SearchFilters(
            category="Flight Controllers",
            availability=ProductStatus.IN_STOCK,
            min_price=Decimal("20000"),
            max_price=Decimal("30000"),
            retailer="Zbotic",
        ),
    )
    assert [item.name for item in combined.items] == ["Holybro Pixhawk 6X"]


async def test_typo_returns_actionable_fuzzy_suggestion(session: AsyncSession) -> None:
    await _catalog(session)

    result = await ProductSearchService().search(session, SearchFilters(query="pixhaw 6x"))

    assert result.items == []
    assert result.suggestion == "Holybro Pixhawk 6X"


async def test_search_is_paginated(session: AsyncSession) -> None:
    await _catalog(session)
    result = await ProductSearchService().search(session, SearchFilters(limit=1, offset=1))
    assert result.total == 3
    assert len(result.items) == 1
