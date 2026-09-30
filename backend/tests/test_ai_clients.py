import inspect
import json

import httpx
import pytest

from app.infra.ai.client.abstract import AIClient
from app.infra.ai.client.deepseek import DeepSeekClient
from app.infra.ai.client.factory import CLIENT_FACTORIES, create_ai_client
from app.infra.ai.client.types import AIRequest, AIResponse
from app.infra.ai.prompt.manager import PromptManager, PromptTemplate
from app.infra.config.settings import Settings
from app.infra.config.types import AIConfig
from app.infra.serializer.error.config import ConfigurationError
from app.services.v2.ai_assist_service import AiAssistService

from .test_ai_assist import ASSESSMENT_INPUT


class AlternateClient(AIClient):
    def __init__(self) -> None:
        self.closed = False

    async def complete(self, request: AIRequest) -> AIResponse:
        assert request.model == "alternate-model"
        assert "student_name" not in json.loads(request.messages[-1].content)
        return AIResponse(
            content=json.dumps(
                {
                    "task_type": "assessment_explanation",
                    "status": "ok",
                    "summary": "这段说明帮助你阅读已经完成的固定结果，并保持原有分层不变，"
                    "你可以按自己的节奏决定是否查看支持资源。",
                    "observations": [],
                    "practical_steps": ["可以先查看支持资源。"],
                    "boundary_notice": "这段说明用于帮助你阅读固定结果，不是诊断或专业评估。",
                }
            ),
            model="alternate-model",
        )

    async def aclose(self) -> None:
        self.closed = True


async def test_provider_can_be_replaced_without_changing_business_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert inspect.isabstract(AIClient)
    alternate = AlternateClient()
    monkeypatch.setitem(CLIENT_FACTORIES, "alternate", lambda config, key: alternate)
    service = AiAssistService(
        Settings(
            ai=AIConfig(
                provider="alternate",
                model="alternate-model",
                resolved_model_version="alternate-v1",
            )
        )
    )
    result = await service.assessment_explanation(
        resource_id="result-1",
        owner_user_id="user-1",
        input_data={**ASSESSMENT_INPUT, "student_name": "private"},
    )
    assert result.status == "adopted"
    assert result.request_model == "alternate-model"
    assert result.resolved_model_version == "alternate-v1"
    await service.aclose()
    assert alternate.closed
    with pytest.raises(ConfigurationError):
        create_ai_client(AIConfig(provider="missing"), api_key=None)


def test_prompt_registry_selects_versions_and_rejects_unknown_or_duplicate_entries() -> None:
    manager = PromptManager(
        (
            PromptTemplate("task", "v1", "first"),
            PromptTemplate("task", "v2", "second"),
        )
    )
    assert manager.get("task", "v2").content == "second"
    with pytest.raises(ConfigurationError):
        manager.get("task", "missing")
    with pytest.raises(ConfigurationError):
        PromptManager(
            (PromptTemplate("task", "v1", "first"), PromptTemplate("task", "v1", "second"))
        )
    assert (
        PromptManager().get("assessment_explanation").content
        != PromptManager().get("treehole_review_assist").content
    )


async def test_deepseek_reuses_client_and_closes_resources() -> None:
    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    client = DeepSeekClient(api_key="test-key", transport=httpx.MockTransport(handler))
    request = PromptManager().request("assessment_explanation", ASSESSMENT_INPUT, AIConfig())
    assert (await client.complete(request)).content == "{}"
    assert (await client.complete(request)).content == "{}"
    assert count == 2
    await client.aclose()
    assert client._client.is_closed
