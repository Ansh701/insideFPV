from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.messaging.base import MessagingDeliveryError, MessagingProvider


class TelegramIncoming(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update_id: int
    telegram_user_id: int
    chat_id: int
    text: str = Field(max_length=2000)
    username: str | None = None
    first_name: str | None = None


class TelegramMessagingProvider(MessagingProvider):
    def __init__(self, bot_token: str | None, *, client: httpx.AsyncClient | None = None) -> None:
        self.bot_token = bot_token
        self.client = client

    async def send_message(self, chat_id: int, text: str) -> str:
        if not self.bot_token:
            raise MessagingDeliveryError("Telegram is not configured.")
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=8)
        try:
            response = await client.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4096], "disable_web_page_preview": True},
            )
            if response.status_code >= 400:
                raise MessagingDeliveryError(f"Telegram returned HTTP {response.status_code}.")
            payload = response.json()
            if not payload.get("ok"):
                raise MessagingDeliveryError("Telegram rejected the message.")
            return str(payload["result"]["message_id"])
        except httpx.HTTPError as exc:
            raise MessagingDeliveryError("Telegram could not be reached.") from exc
        finally:
            if owns_client:
                await client.aclose()

    def parse_incoming(self, update: dict[str, Any]) -> TelegramIncoming:
        message = update.get("message") or update.get("edited_message")
        if not isinstance(message, dict) or not isinstance(message.get("text"), str):
            raise ValueError("Telegram update does not contain a text message.")
        sender = message.get("from")
        chat = message.get("chat")
        if not isinstance(sender, dict) or not isinstance(chat, dict):
            raise ValueError("Telegram update is missing sender or chat information.")
        return TelegramIncoming(
            update_id=int(update["update_id"]),
            telegram_user_id=int(sender["id"]),
            chat_id=int(chat["id"]),
            text=message["text"],
            username=sender.get("username"),
            first_name=sender.get("first_name"),
        )


__all__ = ["MessagingDeliveryError", "TelegramIncoming", "TelegramMessagingProvider"]
