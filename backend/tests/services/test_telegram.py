import json

import httpx
import pytest

from app.messaging.telegram import MessagingDeliveryError, TelegramMessagingProvider


async def test_outbound_telegram_alert_uses_bot_api() -> None:
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = TelegramMessagingProvider("token", client=client)

    message_id = await provider.send_message(123, "Pixhawk is available")

    assert message_id == "42"
    assert requests == [
        {"chat_id": 123, "text": "Pixhawk is available", "disable_web_page_preview": True}
    ]
    await client.aclose()


async def test_failed_outbound_telegram_alert_is_typed() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(503, json={"ok": False}))
    )
    provider = TelegramMessagingProvider("token", client=client)

    with pytest.raises(MessagingDeliveryError, match="HTTP 503"):
        await provider.send_message(123, "hello")
    await client.aclose()


def test_parse_incoming_extracts_minimum_user_data() -> None:
    provider = TelegramMessagingProvider("token")
    incoming = provider.parse_incoming(
        {
            "update_id": 77,
            "message": {
                "text": "/status Pixhawk 6X",
                "chat": {"id": 123},
                "from": {
                    "id": 456,
                    "username": "pilot",
                    "first_name": "Asha",
                    "last_name": "ignored",
                },
            },
        }
    )
    assert incoming.update_id == 77
    assert incoming.telegram_user_id == 456
    assert incoming.text == "/status Pixhawk 6X"
    assert incoming.model_dump().get("last_name") is None
