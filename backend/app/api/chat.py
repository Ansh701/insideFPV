from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ChatRequest, ChatResponse
from app.db import get_session
from app.services.chat import ChatService

router = APIRouter(tags=["chat"])


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    response = await ChatService(
        session,
        llm=request.app.state.llm,
        monitor=request.app.state.monitor,
    ).handle(body.telegram_user_id, body.message)
    return ChatResponse(response=response)
