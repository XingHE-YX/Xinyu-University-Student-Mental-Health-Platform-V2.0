"""Small, fixed-contract DeepSeek HTTP adapter.

The adapter has no business policy: callers must project and validate fields using
``app.services.v2.rules.ai_policy`` before and after invoking it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from pydantic import ValidationError

from app.infra.ai.client.abstract import AIClient
from app.infra.ai.client.types import AIRequest, AIResponse
from app.infra.ai.prompt.templates.common import (
    DEEPSEEK_CHAT_URL,
    DEEPSEEK_MAX_CONCURRENCY,
    DEEPSEEK_TIMEOUT_SECONDS,
)
from app.infra.logger.common import traced
from app.infra.serializer.error.ai import DeepSeekUnavailable as DeepSeekUnavailable


class DeepSeekClient(AIClient):
    def __init__(
        self,
        *,
        api_key: str | None,
        endpoint: str = DEEPSEEK_CHAT_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = DEEPSEEK_TIMEOUT_SECONDS,
        max_concurrency: int = DEEPSEEK_MAX_CONCURRENCY,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._endpoint = endpoint
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._client = httpx.AsyncClient(
            timeout=timeout, transport=transport, follow_redirects=False
        )

    @traced
    async def complete(self, request: AIRequest) -> AIResponse:
        if not self._api_key:
            raise DeepSeekUnavailable("DeepSeek 未配置")
        request_body = {
            "model": request.model,
            "messages": [message.model_dump() for message in request.messages],
            "temperature": request.temperature,
            "stream": False,
        }
        if request.response_format == "json_object":
            request_body["response_format"] = {"type": "json_object"}
        try:
            async with self._semaphore:
                response = await self._client.post(
                    self._endpoint,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=request_body,
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError, ValueError, TypeError:
            raise DeepSeekUnavailable("DeepSeek 请求失败") from None
        content = _extract_content(body)
        if not content:
            raise DeepSeekUnavailable("DeepSeek 返回为空")
        try:
            return AIResponse(content=content, model=body.get("model"), usage=body.get("usage"))
        except ValidationError:
            raise DeepSeekUnavailable("DeepSeek 返回结构不匹配") from None

    @traced
    async def aclose(self) -> None:
        await self._client.aclose()


@traced
def _extract_content(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    return content if isinstance(content, str) else None
