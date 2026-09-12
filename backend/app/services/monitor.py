import asyncio
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.models import (
    Alert,
    AlertDeliveryStatus,
    MonitorRun,
    MonitorRunStatus,
    Product,
    ProductSnapshot,
    ProductStatus,
    WatchlistItem,
    utcnow,
)
from app.services.alerting import AlertDispatcher
from app.services.change_detection import favorable_event, make_event_fingerprint
from app.services.discovery import DiscoveryService
from app.services.llm.service import LLMService
from app.sources.registry import AdapterRegistry

logger = structlog.get_logger()


class TextFetcher(Protocol):
    async def get_text(self, url: str) -> str: ...


@dataclass(frozen=True)
class MonitorResult:
    id: uuid.UUID
    status: str
    products_checked: int
    products_changed: int
    alerts_created: int
    errors_count: int
    error_summary: str | None


@dataclass(frozen=True)
class _ItemResult:
    changed: int = 0
    alerts: tuple[uuid.UUID, ...] = ()
    error: str | None = None


class MonitorService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        registry: AdapterRegistry,
        fetcher: TextFetcher,
        llm: LLMService,
        concurrency: int,
        dispatcher: AlertDispatcher | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.registry = registry
        self.fetcher = fetcher
        self.llm = llm
        self.semaphore = asyncio.Semaphore(concurrency)
        self.dispatcher = dispatcher

    async def run(
        self, *, product_ids: list[uuid.UUID] | None = None, trigger: str = "scheduled"
    ) -> MonitorResult:
        discovery_errors: list[str] = []
        if product_ids is None:
            discovery = await DiscoveryService(
                self.session_factory,
                registry=self.registry,
                fetcher=self.fetcher,
            ).run()
            discovery_errors.extend(discovery.errors)
        async with self.session_factory() as session:
            created_run = MonitorRun(trigger=trigger)
            session.add(created_run)
            await session.commit()
            run_id = created_run.id
            statement = (
                select(Product.id).join(Product.retailer).where(Product.retailer.has(enabled=True))
            )
            if product_ids is not None:
                statement = statement.where(Product.id.in_(product_ids))
            ids = list((await session.scalars(statement)).all())

        results = await asyncio.gather(
            *(self._check_product(run_id, product_id) for product_id in ids)
        )
        errors = discovery_errors + [item.error for item in results if item.error]
        alert_ids = [alert_id for item in results for alert_id in item.alerts]
        if self.dispatcher:
            await asyncio.gather(*(self.dispatcher.deliver(alert_id) for alert_id in alert_ids))
        elif alert_ids:
            async with self.session_factory() as session:
                alerts = list(
                    (await session.scalars(select(Alert).where(Alert.id.in_(alert_ids)))).all()
                )
                for alert in alerts:
                    alert.delivery_status = AlertDeliveryStatus.SKIPPED
                    alert.error = "Telegram delivery is not configured for this monitor instance."
                await session.commit()

        status = MonitorRunStatus.COMPLETED_WITH_ERRORS if errors else MonitorRunStatus.COMPLETED
        async with self.session_factory() as session:
            final_run = await session.get(MonitorRun, run_id)
            assert final_run is not None
            final_run.finished_at = utcnow()
            final_run.status = status
            final_run.products_checked = len(results)
            final_run.products_changed = sum(item.changed for item in results)
            final_run.alerts_created = len(alert_ids)
            final_run.errors_count = len(errors)
            final_run.error_summary = " | ".join(errors)[:4000] if errors else None
            await session.commit()
            return MonitorResult(
                id=final_run.id,
                status=final_run.status.value,
                products_checked=final_run.products_checked,
                products_changed=final_run.products_changed,
                alerts_created=final_run.alerts_created,
                errors_count=final_run.errors_count,
                error_summary=final_run.error_summary,
            )

    async def _check_product(self, run_id: uuid.UUID, product_id: uuid.UUID) -> _ItemResult:
        async with self.semaphore, self.session_factory() as session:
            product = await session.scalar(
                select(Product)
                .options(selectinload(Product.retailer))
                .where(Product.id == product_id)
            )
            if product is None:
                return _ItemResult(error=f"Product {product_id} no longer exists.")
            adapter = self.registry.resolve(product.canonical_url)
            previous = await session.scalar(
                select(ProductSnapshot)
                .where(ProductSnapshot.product_id == product.id, ProductSnapshot.error.is_(None))
                .order_by(ProductSnapshot.checked_at.desc())
                .limit(1)
            )
            try:
                html = await self.fetcher.get_text(product.canonical_url)
                extraction = adapter.parse_product(html, product.canonical_url)
                content_hash = adapter.fingerprint(html)
                if extraction.status is ProductStatus.UNKNOWN:
                    llm_result = await self.llm.classify_product(adapter.normalize_content(html))
                    if llm_result.product_name is None:
                        llm_result.product_name = extraction.product_name
                    if llm_result.price is None:
                        llm_result.price = extraction.price
                    extraction = llm_result
            except Exception as exc:
                safe_error = f"{adapter.name}: {type(exc).__name__}: {str(exc)[:300]}"
                session.add(
                    ProductSnapshot(
                        product_id=product.id,
                        status=ProductStatus.UNKNOWN,
                        currency=product.currency,
                        attributes={},
                        classification_source="ERROR",
                        confidence=Decimal("0"),
                        content_hash="0" * 64,
                        error=safe_error,
                    )
                )
                product.last_checked_at = utcnow()
                await session.commit()
                logger.warning(
                    "monitor_product",
                    monitor_run_id=str(run_id),
                    product_id=str(product_id),
                    retailer=adapter.name,
                    status="error",
                )
                return _ItemResult(error=safe_error)

            old_status = previous.status if previous else None
            old_price = previous.price if previous else None
            snapshot = ProductSnapshot(
                product_id=product.id,
                status=extraction.status,
                price=extraction.price,
                currency=extraction.currency,
                attributes=extraction.attributes,
                classification_source=extraction.classification_source,
                classification_provider=extraction.provider,
                confidence=Decimal(str(extraction.confidence)),
                content_hash=content_hash,
            )
            session.add(snapshot)
            await session.flush()
            product.name = extraction.product_name or product.name
            product.normalized_name = product.name.lower()
            product.manufacturer = extraction.manufacturer or product.manufacturer
            product.category = extraction.category or product.category
            product.current_status = extraction.status
            product.current_price = extraction.price
            product.currency = extraction.currency
            product.attributes = extraction.attributes
            product.content_hash = content_hash
            product.last_checked_at = snapshot.checked_at
            changed = int(
                previous is not None
                and (old_status != snapshot.status or old_price != snapshot.price)
            )
            event = favorable_event(old_status, snapshot.status)
            alert_ids: list[uuid.UUID] = []
            if event and previous and old_status:
                watches = list(
                    (
                        await session.scalars(
                            select(WatchlistItem).where(
                                WatchlistItem.product_id == product.id,
                                WatchlistItem.enabled.is_(True),
                            )
                        )
                    ).all()
                )
                for watch in watches:
                    alert = Alert(
                        user_id=watch.telegram_user_id,
                        product_id=product.id,
                        snapshot_id=snapshot.id,
                        event_type=event,
                        event_fingerprint=make_event_fingerprint(
                            watch.telegram_user_id,
                            product.id,
                            previous.id,
                            old_status,
                            snapshot.status,
                            content_hash,
                        ),
                    )
                    try:
                        async with session.begin_nested():
                            session.add(alert)
                            await session.flush()
                    except IntegrityError:
                        continue
                    alert_ids.append(alert.id)
            await session.commit()
            logger.info(
                "monitor_product",
                monitor_run_id=str(run_id),
                product_id=str(product_id),
                retailer=adapter.name,
                status=extraction.status.value,
            )
            return _ItemResult(changed=changed, alerts=tuple(alert_ids))
