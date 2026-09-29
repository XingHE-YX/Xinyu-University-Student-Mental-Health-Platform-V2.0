"""Small, fixed-contract DeepSeek HTTP adapter.

The adapter has no business policy: callers must project and validate fields using
``app.domain.ai_policy`` before and after invoking it.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

import httpx

from app.config.ai_prompt import (
    DEEPSEEK_CHAT_URL,
    DEEPSEEK_MAX_CONCURRENCY,
    DEEPSEEK_TIMEOUT_SECONDS,
    REQUEST_MODEL,
    SYSTEM_PROMPT,
)


class DeepSeekUnavailable(RuntimeError):
    """Raised when DeepSeek cannot produce a usable JSON response."""


class DeepSeekClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        endpoint: str = DEEPSEEK_CHAT_URL,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = DEEPSEEK_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key.strip() if api_key else None
        self._endpoint = endpoint
        self._transport = transport
        self._timeout = timeout
        self._semaphore = asyncio.Semaphore(DEEPSEEK_MAX_CONCURRENCY)

    async def complete(self, *, task_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if not self._api_key:
            raise DeepSeekUnavailable("DeepSeek 未配置")
        request_body = {
            "model": REQUEST_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(dict(payload), ensure_ascii=False)},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        try:
            async with self._semaphore:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    transport=self._transport,
                ) as client:
                    response = await client.post(
                        self._endpoint,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json=request_body,
                    )
                    response.raise_for_status()
                    body = response.json()
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise DeepSeekUnavailable("DeepSeek 请求失败") from error
        content = _extract_content(body)
        if not content:
            raise DeepSeekUnavailable("DeepSeek 返回为空")
        try:
            parsed = json.loads(content)
        except (TypeError, json.JSONDecodeError) as error:
            raise DeepSeekUnavailable("DeepSeek 返回不是合法 JSON") from error
        if not isinstance(parsed, dict) or parsed.get("task_type") != task_type:
            raise DeepSeekUnavailable("DeepSeek 返回结构不匹配")
        return parsed


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
