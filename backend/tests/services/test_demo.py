import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.models import Product, ProductStatus
from app.scripts.demo_monitor import run_demo
from app.services.seed import seed_database


async def test_demo_requires_explicit_demo_mode(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(RuntimeError, match="DEMO_MODE"):
        await run_demo(
            Settings(app_env="test", database_url="sqlite+aiosqlite://"), session_factory
        )


async def test_demo_uses_real_baseline_then_transition_pipeline(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await seed_database(session)
    settings = Settings(app_env="test", database_url="sqlite+aiosqlite://", demo_mode=True)

    first = await run_demo(settings, session_factory)
    second = await run_demo(settings, session_factory)

    async with session_factory() as session:
        product = await session.scalar(select(Product).where(Product.name == "Holybro Pixhawk 6X"))
        assert first.status_before is None
        assert first.status_after is ProductStatus.OUT_OF_STOCK
        assert first.monitor.alerts_created == 0
        assert second.status_before is ProductStatus.OUT_OF_STOCK
        assert second.status_after is ProductStatus.IN_STOCK
        assert second.monitor.alerts_created == 1
        assert product is not None and product.current_status is ProductStatus.IN_STOCK
