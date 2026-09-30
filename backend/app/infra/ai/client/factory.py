"""Providers are selected by validated code configuration."""

from collections.abc import Callable

from app.infra.ai.client.abstract import AIClient
from app.infra.ai.client.deepseek import DeepSeekClient
from app.infra.config.types import AIConfig
from app.infra.logger.common import traced
from app.infra.serializer.error.config import ConfigurationError

type ClientFactory = Callable[[AIConfig, str | None], AIClient]


@traced
def _deepseek(config: AIConfig, api_key: str | None) -> AIClient:
    return DeepSeekClient(
        api_key=api_key,
        endpoint=config.endpoint,
        timeout=config.timeout_seconds,
        max_concurrency=config.max_concurrency,
    )


CLIENT_FACTORIES: dict[str, ClientFactory] = {"deepseek": _deepseek}


@traced
def create_ai_client(config: AIConfig, *, api_key: str | None) -> AIClient:
    factory = CLIENT_FACTORIES.get(config.provider)
    if factory is None:
        raise ConfigurationError("AI provider is not registered")
    return factory(config, api_key)
