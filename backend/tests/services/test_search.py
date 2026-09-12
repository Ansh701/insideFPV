from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product, ProductSnapshot, ProductStatus, Retailer
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
            Product(
                retailer_id=robu.id,
                canonical_url="https://robu.in/product/random-screws",
                name="M3 Random Screws",
                normalized_name="m3 random screws",
                category="Other",
                current_status=ProductStatus.IN_STOCK,
                current_price=Decimal("99"),
            ),
            Product(
                retailer_id=robu.id,
                canonical_url="https://robu.in/product/unpriced-pi",
                name="Raspberry Pi Compute Module",
                normalized_name="raspberry pi compute module",
                category="Companion Computers",
                current_status=ProductStatus.UNKNOWN,
                current_price=None,
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
    assert result.total == 4
    assert len(result.items) == 1


async def test_default_search_hides_other_but_explicit_other_remains_queryable(
    session: AsyncSession,
) -> None:
    await _catalog(session)
    service = ProductSearchService()

    default_result = await service.search(session, SearchFilters())
    other_result = await service.search(session, SearchFilters(category="Other"))

    assert all(item.category != "Other" for item in default_result.items)
    assert [item.name for item in other_result.items] == ["M3 Random Screws"]


async def test_price_filter_excludes_unknown_prices_and_exposes_safe_latest_error(
    session: AsyncSession,
) -> None:
    await _catalog(session)
    unpriced = await session.scalar(
        select(Product).where(Product.name == "Raspberry Pi Compute Module")
    )
    assert unpriced is not None
    session.add(
        ProductSnapshot(
            product_id=unpriced.id,
            status=ProductStatus.UNKNOWN,
            classification_source="ERROR",
            content_hash="0" * 64,
            error="ThinkRobotics: RetailerFetchError: Retailer responded with HTTP 403.",
        )
    )
    await session.commit()

    result = await ProductSearchService().search(session, SearchFilters(max_price=Decimal("15000")))
    diagnostic = await ProductSearchService().search(session, SearchFilters(query="Compute Module"))

    assert all(item.price is not None for item in result.items)
    assert diagnostic.items[0].latest_check_error == (
        "The retailer blocked the automated request (HTTP 403)."
    )
    assert "RetailerFetchError" not in (diagnostic.items[0].latest_check_error or "")
