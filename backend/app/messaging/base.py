from abc import ABC, abstractmethod


class MessagingDeliveryError(RuntimeError):
    pass


class MessagingProvider(ABC):
    @abstractmethod
    async def send_message(self, chat_id: int, text: str) -> str:
        raise NotImplementedError
