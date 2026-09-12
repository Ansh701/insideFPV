from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_admin
from app.db import get_session
from app.models import Alert, MonitorRun, Product, ProductStatus, WatchlistItem

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard/summary")
async def dashboard_summary(session: AsyncSession = Depends(get_session)) -> dict[str, object]:
    latest = await session.scalar(
        select(MonitorRun).order_by(MonitorRun.started_at.desc()).limit(1)
    )
    status_counts: dict[ProductStatus, int] = {}
    count_rows = (
        await session.execute(
            select(Product.current_status, func.count()).group_by(Product.current_status)
        )
    ).all()
    for product_status, count in count_rows:
        status_counts[product_status] = int(count)
    watched = int(
        await session.scalar(
            select(func.count()).select_from(WatchlistItem).where(WatchlistItem.enabled.is_(True))
        )
        or 0
    )
    return {
        "watched_products": watched,
        "in_stock": status_counts.get(ProductStatus.IN_STOCK, 0),
        "preorders": status_counts.get(ProductStatus.PREORDER, 0),
        "unknown_or_problems": status_counts.get(ProductStatus.UNKNOWN, 0),
        "last_run": (
            {
                "id": latest.id,
                "status": latest.status,
                "started_at": latest.started_at,
                "finished_at": latest.finished_at,
                "products_checked": latest.products_checked,
                "errors_count": latest.errors_count,
            }
            if latest
            else None
        ),
    }


@router.get("/api/alerts")
async def list_alerts(
    limit: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    rows = (
        await session.execute(
            select(Alert, Product)
            .join(Product, Alert.product_id == Product.id)
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )
    ).all()
    return {
        "items": [
            {
                "id": alert.id,
                "product_name": product.name,
                "product_id": product.id,
                "event_type": alert.event_type,
                "delivery_status": alert.delivery_status,
                "created_at": alert.created_at,
                "delivered_at": alert.delivered_at,
                "error": alert.error,
            }
            for alert, product in rows
        ]
    }


@router.post(
    "/api/admin/alerts/retry",
    dependencies=[Depends(require_admin)],
    response_model=None,
)
async def retry_failed_alerts(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
) -> dict[str, int] | JSONResponse:
    dispatcher = request.app.state.alert_dispatcher
    if dispatcher is None:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "TELEGRAM_NOT_CONFIGURED",
                    "message": (
                        "Failed alerts cannot be retried because Telegram is not configured."
                    ),
                    "action": "Configure TELEGRAM_BOT_TOKEN, restart the service, and retry.",
                }
            },
        )
    result = await dispatcher.retry_failed(limit=limit)
    return {
        "attempted": result.attempted,
        "sent": result.sent,
        "failed": result.failed,
    }
