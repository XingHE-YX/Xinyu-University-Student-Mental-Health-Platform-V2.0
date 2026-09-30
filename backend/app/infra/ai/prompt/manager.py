"""Versioned task prompts are independent of the selected AI provider."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from app.infra.ai.client.types import AIMessage, AIRequest
from app.infra.ai.prompt.templates.assessment_explanation import PROMPT as ASSESSMENT_PROMPT
from app.infra.ai.prompt.templates.common import PROMPT_VERSION
from app.infra.ai.prompt.templates.treehole_review_assist import PROMPT as TREEHOLE_PROMPT
from app.infra.config.types import AIConfig
from app.infra.logger.common import traced
from app.infra.serializer.error.config import ConfigurationError


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    task_type: str
    version: str
    content: str


class PromptManager:
    def __init__(self, templates: tuple[PromptTemplate, ...] | None = None) -> None:
        actual = (
            templates
            if templates is not None
            else (
                PromptTemplate("assessment_explanation", PROMPT_VERSION, ASSESSMENT_PROMPT),
                PromptTemplate("treehole_review_assist", PROMPT_VERSION, TREEHOLE_PROMPT),
            )
        )
        registry = {(item.task_type, item.version): item for item in actual}
        if len(registry) != len(actual):
            raise ConfigurationError("duplicate prompt task and version")
        self.templates = MappingProxyType(registry)

    @traced
    def get(self, task_type: str, version: str = PROMPT_VERSION) -> PromptTemplate:
        template = self.templates.get((task_type, version))
        if template is None:
            raise ConfigurationError("prompt task or version is not registered")
        return template

    @traced
    def request(self, task_type: str, payload: Mapping[str, Any], config: AIConfig) -> AIRequest:
        template = self.get(task_type)
        return AIRequest(
            model=config.model,
            temperature=config.temperature,
            messages=(
                AIMessage(role="system", content=template.content),
                AIMessage(role="user", content=json.dumps(dict(payload), ensure_ascii=False)),
            ),
        )
