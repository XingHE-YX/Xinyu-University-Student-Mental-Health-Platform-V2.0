"""All AI providers implement the same asynchronous resource contract."""

from abc import ABC, abstractmethod

from app.infra.ai.client.types import AIRequest, AIResponse


class AIClient(ABC):
    @abstractmethod
    async def complete(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError

    @abstractmethod
    async def aclose(self) -> None:
        raise NotImplementedError
