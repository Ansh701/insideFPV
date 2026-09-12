import asyncio
import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.db import SessionFactory
from app.models import Product, ProductSnapshot, ProductStatus
from app.services.llm.factory import build_llm_service
from app.services.monitor import MonitorResult, MonitorService
from app.sources.registry import default_registry


class DemoFixtureFetcher:
    def __init__(self, status: ProductStatus) -> None:
        self.status = status

    async def get_text(self, url: str) -> str:
        availability = {
            ProductStatus.OUT_OF_STOCK: "OutOfStock",
            ProductStatus.IN_STOCK: "InStock",
            ProductStatus.PREORDER: "PreOrder",
            ProductStatus.UNKNOWN: "Discontinued",
        }[self.status]
        return f"""<!doctype html><html><head><script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Product","name":"Holybro Pixhawk 6X",
"brand":{{"name":"Holybro"}},"category":"Flight Controllers",
"offers":{{"price":"25198.95","priceCurrency":"INR","availability":"https://schema.org/{availability}","url":"{url}"}}}}
</script></head><body><main><h1>Holybro Pixhawk 6X</h1></main></body></html>"""


@dataclass(frozen=True)
class DemoResult:
    status_before: ProductStatus | None
    status_after: ProductStatus
    monitor: MonitorResult


async def run_demo(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> DemoResult:
    if not settings.demo_mode or settings.app_env == "production":
        raise RuntimeError(
            "Set DEMO_MODE=true outside production to run deterministic demo monitoring."
        )
    async with session_factory() as session:
        product = await session.scalar(select(Product).where(Product.name == "Holybro Pixhawk 6X"))
        if product is None:
            raise RuntimeError("Seed the database before running the demo.")
        previous = await session.scalar(
            select(ProductSnapshot)
            .where(ProductSnapshot.product_id == product.id, ProductSnapshot.error.is_(None))
            .order_by(ProductSnapshot.checked_at.desc())
            .limit(1)
        )
        status_before = previous.status if previous else None
        next_status = (
            ProductStatus.IN_STOCK
            if status_before is ProductStatus.OUT_OF_STOCK
            else ProductStatus.OUT_OF_STOCK
        )
        product_id = product.id

    service = MonitorService(
        session_factory,
        registry=default_registry(),
        fetcher=DemoFixtureFetcher(next_status),
        llm=build_llm_service(settings),
        concurrency=1,
    )
    result = await service.run(product_ids=[product_id], trigger="demo")
    return DemoResult(status_before=status_before, status_after=next_status, monitor=result)


async def run() -> None:
    result = await run_demo(get_settings(), SessionFactory)
    print(json.dumps({**result.__dict__, "monitor": result.monitor.__dict__}, default=str))


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
