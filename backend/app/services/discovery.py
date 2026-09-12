from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol
from urllib.parse import unquote, urlsplit

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import CategoryWatch, Product, Retailer, utcnow
from app.services.url_security import normalize_supported_url
from app.sources.registry import AdapterRegistry

logger = structlog.get_logger()


class DiscoveryFetcher(Protocol):
    async def get_text(self, url: str) -> str: ...


@dataclass(frozen=True)
class DiscoveryResult:
    categories_scanned: int
    products_discovered: int
    errors: tuple[str, ...]


def _name_from_url(url: str) -> str:
    slug = PurePosixPath(urlsplit(url).path.rstrip("/")).name
    words = unquote(slug).replace("-", " ").replace("_", " ").split()
    return " ".join(
        word.upper() if word.lower() in {"fpv", "gps", "rf"} else word.title() for word in words
    )


class DiscoveryService:
    """Bounded category-page discovery; it never crawls beyond adapter product links."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        registry: AdapterRegistry,
        fetcher: DiscoveryFetcher,
    ) -> None:
        self.session_factory = session_factory
        self.registry = registry
        self.fetcher = fetcher

    async def run(self) -> DiscoveryResult:
        discovered = 0
        scanned = 0
        errors: list[str] = []
        async with self.session_factory() as session:
            watches = list(
                (
                    await session.execute(
                        select(
                            CategoryWatch.id,
                            CategoryWatch.retailer_id,
                            Retailer.name,
                            CategoryWatch.category,
                            CategoryWatch.source_url,
                        )
                        .join(Retailer, Retailer.id == CategoryWatch.retailer_id)
                        .where(
                            CategoryWatch.enabled.is_(True), CategoryWatch.source_url.is_not(None)
                        )
                    )
                ).all()
            )
            existing_urls = set((await session.scalars(select(Product.canonical_url))).all())
        for watch_id, retailer_id, retailer_name, category, source_url in watches:
            assert source_url is not None
            try:
                adapter = self.registry.resolve(source_url)
                html = await self.fetcher.get_text(source_url)
                urls = adapter.discover_products(html, source_url, limit=50)
                async with self.session_factory() as session:
                    scanned += 1
                    for url in urls:
                        canonical_url = normalize_supported_url(url, self.registry.domains).rstrip(
                            "/"
                        )
                        if canonical_url in existing_urls:
                            continue
                        session.add(
                            Product(
                                retailer_id=retailer_id,
                                canonical_url=canonical_url,
                                name=_name_from_url(canonical_url),
                                normalized_name=_name_from_url(canonical_url).lower(),
                                category=category,
                            )
                        )
                        existing_urls.add(canonical_url)
                        discovered += 1
                    stored_watch = await session.get(CategoryWatch, watch_id)
                    if stored_watch is not None:
                        stored_watch.last_scanned_at = utcnow()
                    await session.commit()
            except Exception as exc:
                safe_error = f"{retailer_name} discovery: {type(exc).__name__}: {str(exc)[:240]}"
                errors.append(safe_error)
                logger.warning("category_discovery", retailer=retailer_name, status="error")
        return DiscoveryResult(scanned, discovered, tuple(errors))
