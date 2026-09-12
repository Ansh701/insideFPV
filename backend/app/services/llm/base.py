from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class ProviderFailure(RuntimeError):
    def __init__(self, message: str, *, retryable: bool, category: str) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.category = category


class LLMProvider(ABC):
    name: str
    model: str
    is_configured: bool

    @abstractmethod
    async def generate_json(self, purpose: str, prompt: str) -> Mapping[str, Any]:
        raise NotImplementedError
