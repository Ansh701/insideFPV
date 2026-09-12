from sqlalchemy.ext.asyncio import AsyncSession

from app.services.seed import seed_database
from app.services.watchlist import DuplicateWatchError, WatchlistService, WatchTargetError


async def test_add_known_product_prevents_duplicate_and_remove_persists(
    session: AsyncSession,
) -> None:
    await seed_database(session)
    service = WatchlistService()

    seeded = next(
        item
        for item in await service.list(session, telegram_user_id=0)
        if item.product.name == "Raspberry Pi 5"
    )
    await service.remove(session, telegram_user_id=0, watch_id=seeded.id)
    item = await service.add(session, telegram_user_id=0, product_name="Raspberry Pi 5")
    try:
        await service.add(session, telegram_user_id=0, product_name="Raspberry Pi 5")
    except DuplicateWatchError:
        pass
    else:
        raise AssertionError("duplicate watch should be rejected")

    assert len(await service.list(session, telegram_user_id=0)) == 3
    await service.remove(session, telegram_user_id=0, watch_id=item.id)
    assert len(await service.list(session, telegram_user_id=0)) == 2


async def test_add_supported_url_creates_dynamic_unknown_product(session: AsyncSession) -> None:
    await seed_database(session)

    item = await WatchlistService().add(
        session,
        telegram_user_id=0,
        url="https://zbotic.in/product/another-pixhawk/?utm_source=chat",
    )

    assert item.product.canonical_url == "https://zbotic.in/product/another-pixhawk"
    assert item.product.name == "Another Pixhawk"


async def test_unsupported_and_unsafe_watch_urls_are_rejected(session: AsyncSession) -> None:
    await seed_database(session)
    service = WatchlistService()
    for value in ("https://example.com/product/a", "http://127.0.0.1/a", "file:///tmp/a", "broken"):
        try:
            await service.add(session, telegram_user_id=0, url=value)
        except WatchTargetError:
            continue
        raise AssertionError(f"unsafe URL was accepted: {value}")
