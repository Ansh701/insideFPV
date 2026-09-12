import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import WatchCreate, WatchResponse
from app.db import get_session
from app.models import WatchlistItem
from app.services.watchlist import (
    DuplicateWatchError,
    WatchlistService,
    WatchNotFoundError,
    WatchTargetError,
)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def _response(item: WatchlistItem) -> WatchResponse:
    product = item.product
    return WatchResponse(
        id=item.id,
        product_id=product.id,
        product_name=product.name,
        retailer=product.retailer.name,
        status=product.current_status,
        price=product.current_price,
        canonical_url=product.canonical_url,
        enabled=item.enabled,
        created_at=item.created_at,
    )


@router.get("", response_model=list[WatchResponse])
async def list_watches(
    telegram_user_id: int = Query(default=0), session: AsyncSession = Depends(get_session)
) -> list[WatchResponse]:
    items = await WatchlistService().list(session, telegram_user_id=telegram_user_id)
    return [_response(item) for item in items]


@router.post("", response_model=WatchResponse, status_code=201)
async def add_watch(
    body: WatchCreate, session: AsyncSession = Depends(get_session)
) -> WatchResponse | JSONResponse:
    try:
        item = await WatchlistService().add(
            session,
            telegram_user_id=body.telegram_user_id,
            product_name=body.product_name,
            url=body.url,
        )
    except (WatchTargetError, DuplicateWatchError) as exc:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_WATCH_TARGET",
                    "message": str(exc),
                    "action": (
                        "Use a product name already in the catalog or a URL from a "
                        "supported retailer."
                    ),
                }
            },
        )
    await session.refresh(item, attribute_names=["product"])
    await session.refresh(item.product, attribute_names=["retailer"])
    return _response(item)


@router.delete("/{watch_id}", response_model=None)
async def remove_watch(
    watch_id: uuid.UUID,
    telegram_user_id: int = Query(default=0),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str] | JSONResponse:
    try:
        await WatchlistService().remove(
            session, telegram_user_id=telegram_user_id, watch_id=watch_id
        )
    except WatchNotFoundError as exc:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "WATCH_NOT_FOUND",
                    "message": str(exc),
                    "action": "Refresh the watchlist and choose an active item.",
                }
            },
        )
    return {"status": "removed"}
