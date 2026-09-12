import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.messaging.base import MessagingDeliveryError, MessagingProvider
from app.models import Alert, AlertDeliveryStatus, Product, Retailer, TelegramUser, utcnow


@dataclass(frozen=True)
class AlertRetryResult:
    attempted: int
    sent: int
    failed: int


class AlertDispatcher:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        messaging: MessagingProvider,
    ) -> None:
        self.session_factory = session_factory
        self.messaging = messaging

    async def deliver(self, alert_id: uuid.UUID) -> None:
        async with self.session_factory() as session:
            row = (
                await session.execute(
                    select(Alert, Product, Retailer, TelegramUser)
                    .join(Product, Alert.product_id == Product.id)
                    .join(Retailer, Product.retailer_id == Retailer.id)
                    .join(TelegramUser, Alert.user_id == TelegramUser.id)
                    .where(Alert.id == alert_id)
                )
            ).one()
            alert, product, retailer, user = row
            event = (
                "is back in stock"
                if alert.event_type.value == "BACK_IN_STOCK"
                else "pre-order opened"
            )
            price = (
                f"₹{product.current_price:,.2f}"
                if product.current_price is not None
                else "Not listed"
            )
            checked = product.last_checked_at.isoformat() if product.last_checked_at else "just now"
            message = (
                f"{product.name} {event}\n"
                f"Price: {price}\n"
                f"Retailer: {retailer.name}\n"
                f"Checked: {checked}\n"
                f"View product: {product.canonical_url}"
            )
            try:
                await self.messaging.send_message(user.chat_id, message)
            except MessagingDeliveryError as exc:
                alert.delivery_status = AlertDeliveryStatus.FAILED
                alert.error = str(exc)[:1000]
            else:
                alert.delivery_status = AlertDeliveryStatus.SENT
                alert.delivered_at = utcnow()
                alert.error = None
            await session.commit()

    async def retry_failed(self, *, limit: int = 25) -> AlertRetryResult:
        async with self.session_factory() as session:
            alert_ids = list(
                (
                    await session.scalars(
                        select(Alert.id)
                        .where(Alert.delivery_status == AlertDeliveryStatus.FAILED)
                        .order_by(Alert.created_at)
                        .limit(limit)
                    )
                ).all()
            )
        for alert_id in alert_ids:
            await self.deliver(alert_id)
        if not alert_ids:
            return AlertRetryResult(attempted=0, sent=0, failed=0)
        async with self.session_factory() as session:
            statuses = list(
                (
                    await session.scalars(
                        select(Alert.delivery_status).where(Alert.id.in_(alert_ids))
                    )
                ).all()
            )
        sent = sum(status is AlertDeliveryStatus.SENT for status in statuses)
        return AlertRetryResult(
            attempted=len(alert_ids),
            sent=sent,
            failed=len(alert_ids) - sent,
        )
