import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import TelegramUpdate
from app.db import get_session
from app.models import ProcessedTelegramUpdate
from app.services.chat import ChatService
from app.services.watchlist import WatchlistService

router = APIRouter(tags=["telegram"])


@router.post("/webhooks/telegram")
async def telegram_webhook(
    body: TelegramUpdate,
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    expected = request.app.state.settings.telegram_webhook_secret
    if expected and (
        x_telegram_bot_api_secret_token is None
        or not secrets.compare_digest(x_telegram_bot_api_secret_token, expected)
    ):
        raise HTTPException(status_code=401, detail="Invalid Telegram webhook secret.")
    try:
        incoming = request.app.state.telegram.parse_incoming(body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session.add(ProcessedTelegramUpdate(update_id=incoming.update_id))
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return {"status": "duplicate"}
    await WatchlistService().ensure_user(
        session,
        incoming.telegram_user_id,
        chat_id=incoming.chat_id,
        username=incoming.username,
        first_name=incoming.first_name,
    )
    await session.commit()
    response = await ChatService(
        session,
        llm=request.app.state.llm,
        monitor=request.app.state.monitor,
    ).handle(incoming.telegram_user_id, incoming.text)
    try:
        await request.app.state.telegram.send_message(incoming.chat_id, response)
    except Exception:
        # Business processing stays committed; delivery can be retried without repeating commands.
        return {"status": "processed", "delivery": "failed"}
    return {"status": "processed"}
