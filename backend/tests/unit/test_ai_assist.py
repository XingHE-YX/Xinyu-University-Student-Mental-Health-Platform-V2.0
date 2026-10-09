import json
from typing import Any

import httpx
import pytest

from app.infra.ai.client.abstract import AIClient
from app.infra.ai.client.deepseek import DeepSeekClient, DeepSeekUnavailable
from app.infra.ai.client.types import AIRequest, AIResponse
from app.infra.ai.prompt.manager import PromptManager
from app.infra.config.settings import Settings
from app.infra.config.types import AIConfig
from app.infra.database.common import RepositoryUnavailable
from app.infra.database.memory.audit import InMemoryAuditRepository
from app.infra.database.memory.domain import InMemoryDomainDataRepository
from app.infra.database.records import AuditEventRecord
from app.infra.logger.audit import AuditWriter
from app.services.v2.ai_assist_service import AiAssistService
from app.services.v2.rules.ai_policy import (
    PolicyViolation,
    project_assessment_input,
    project_treehole_input,
    validate_ai_output,
)


def settings_for(*, api_key: str | None = "deepseek-secret") -> Settings:
    values = {
        "WECHAT_APPID": "wx-demo",
        "WECHAT_APPSECRET": "wechat-secret",
        "CLOUDBASE_ENV_ID": "demo-env",
        "CLOUDBASE_API_KEY": "cloudbase-secret",
        "DEEPSEEK_API_KEY": api_key or "",
        "ADMIN_PASSWORD_HASH": "pbkdf2_sha256$1$salt$digest",
        "ADMIN_SESSION_SECRET": "admin-session-secret",
        "SCHOOL_IDENTITY_PROVIDER_URL": "https://identity.example.test",
        "SUPPORT_RESOURCE_VERSION": "support-v1",
        "DEMO_MODE": "true",
    }
    return Settings.from_environment(values, demo_env_ids={"demo-env"})


ASSESSMENT_INPUT: dict[str, Any] = {
    "task_type": "assessment_explanation",
    "module": "GAD7",
    "score": 11,
    "max_score": 21,
    "fixed_band": "近期焦虑相关困扰较明显，建议查看支持资源",
    "fixed_summary": "这次记录显示，过去两周紧绷和担心对你有一些明显影响。",
    "derived_facts": ["放松相关回答较突出", "担心相关回答较突出"],
    "allowed_steps": ["查看支持资源", "和可信任的人聊一聊", "在合适时联系专业人员"],
}


TREEHOLE_INPUT: dict[str, Any] = {
    "task_type": "treehole_review_assist",
    "content_type": "post",
    "topic": "学业压力",
    "sanitized_text": "最近作业很多，我有点撑不住，想找人说说。［已隐藏的联系方式］",
    "rule_flags": ["possible_contact_residue"],
    "protect_supported": True,
}


def test_input_projection_removes_identity_answers_and_safety_fields() -> None:
    projected = project_assessment_input(
        {
            **ASSESSMENT_INPUT,
            "student_name": "不应发送",
            "student_number": "20240001",
            "answers": [{"question_key": "q1", "option_key": "3"}],
        }
    )

    assert projected == ASSESSMENT_INPUT
    assert "student_name" not in projected
    assert "answers" not in projected


def test_assessment_projection_rejects_safety_confirmation_fields() -> None:
    with pytest.raises(PolicyViolation, match="安全确认"):
        project_assessment_input({**ASSESSMENT_INPUT, "safety_confirmation": "cannot_be_safe"})


def test_treehole_projection_rejects_residual_phone_number() -> None:
    with pytest.raises(PolicyViolation, match="脱敏"):
        project_treehole_input({**TREEHOLE_INPUT, "sanitized_text": "请联系 13800138000"})


def test_output_policy_rejects_unknown_fields_and_evidence_not_in_text() -> None:
    output = {
        "task_type": "treehole_review_assist",
        "status": "ok",
        "content_safety": "clear",
        "wellbeing_signal": "none",
        "privacy_signal": "clear",
        "community_issue": ["none"],
        "evidence_spans": ["不存在的片段"],
        "recommended_route": "allow",
        "review_note": "已完成基础初筛。",
        "unexpected": "不要接受",
    }

    with pytest.raises(PolicyViolation):
        validate_ai_output(
            "treehole_review_assist",
            output,
            source_text=TREEHOLE_INPUT["sanitized_text"],
            content_type="post",
        )


async def test_deepseek_client_sends_fixed_json_contract_without_retry() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"task_type": "assessment_explanation"})}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = DeepSeekClient(api_key="secret", transport=transport)
    result = await client.complete(
        PromptManager().request(
            "assessment_explanation", {"task_type": "assessment_explanation"}, AIConfig()
        ),
    )

    assert json.loads(result.content) == {"task_type": "assessment_explanation"}
    assert len(requests) == 1
    assert requests[0].url == "https://api.deepseek.com/chat/completions"
    assert requests[0].headers["authorization"] == "Bearer secret"
    body = json.loads(requests[0].content)
    assert body["model"] == "deepseek-v4-flash"
    assert body["temperature"] == 0.2
    assert body["stream"] is False
    assert body["response_format"] == {"type": "json_object"}


async def test_missing_key_is_explicit_unavailable() -> None:
    client = DeepSeekClient(api_key=None)
    with pytest.raises(DeepSeekUnavailable, match="未配置"):
        await client.complete(
            PromptManager().request("assessment_explanation", ASSESSMENT_INPUT, AIConfig())
        )


async def test_service_falls_back_and_audits_without_blocking_fixed_result() -> None:
    audit_repository = InMemoryAuditRepository()
    settings = settings_for(api_key=None)
    assert settings.configuration_status == "ready"
    service = AiAssistService(
        settings,
        audit_writer=AuditWriter(audit_repository, environment_id="demo-env"),
    )

    result = await service.assessment_explanation(
        resource_id="result-1",
        owner_user_id="user-1",
        input_data=ASSESSMENT_INPUT,
    )

    assert result.status == "fallback"
    assert result.output is None
    assert result.fallback_reason == "dependency_unavailable"
    assert result.fixed_result_available is True
    event = (await audit_repository.list())[0]
    assert event.action == "ai_assist"
    assert event.details["task_kind"] == "assessment_explanation"
    assert event.details["outcome_category"] == "fallback"
    assert "fixed_summary" not in event.details


async def test_service_adopts_valid_output_but_does_not_change_fixed_band() -> None:
    output = {
        "task_type": "assessment_explanation",
        "status": "ok",
        "summary": (
            "这段说明帮助你阅读已经完成的固定结果，内容保持平静并只基于本次记录，"
            "不改变固定分层，也不替代你对下一步的自主决定。"
        ),
        "observations": ["近期担心和放松相关回答较突出。"],
        "practical_steps": ["可以先查看支持资源，再按自己的节奏决定下一步。"],
        "boundary_notice": "这段说明用于帮助你阅读固定结果，不是诊断或专业评估。",
    }

    class StubClient(AIClient):
        async def complete(self, request: AIRequest) -> AIResponse:
            payload = json.loads(request.messages[-1].content)
            task_type = payload["task_type"]
            assert task_type == "assessment_explanation"
            assert payload == ASSESSMENT_INPUT
            return AIResponse(content=json.dumps(output, ensure_ascii=False), model="fake-model")

        async def aclose(self) -> None:
            pass

    service = AiAssistService(settings_for(), client=StubClient())
    result = await service.assessment_explanation(
        resource_id="result-1",
        owner_user_id="user-1",
        input_data=ASSESSMENT_INPUT,
    )

    assert result.status == "adopted"
    assert result.output == output
    assert result.fixed_result_available is True
    assert result.fixed_band_unchanged == ASSESSMENT_INPUT["fixed_band"]


async def test_treehole_failure_requests_manual_review_and_never_publishes() -> None:
    settings = settings_for(api_key=None)
    assert settings.configuration_status == "ready"
    service = AiAssistService(settings)
    result = await service.treehole_review_assist(
        resource_id="post-1",
        input_data=TREEHOLE_INPUT,
    )

    assert result.status == "fallback"
    assert result.manual_review_required is True
    assert result.recommended_route == "manual_review"
    assert result.visibility_state == "pending_confirmation"


async def test_needs_fallback_model_response_is_not_adopted() -> None:
    class FallbackClient(AIClient):
        async def complete(self, request: AIRequest) -> AIResponse:
            payload = json.loads(request.messages[-1].content)
            task_type = payload["task_type"]
            del task_type, payload
            return AIResponse(
                content=json.dumps(
                    {
                        "task_type": "assessment_explanation",
                        "status": "needs_fallback",
                        "summary": (
                            "这段说明帮助你阅读已经完成的固定结果，内容保持平静并只基于本次记录，"
                            "不改变固定分层，也不替代你对下一步的自主决定。"
                        ),
                        "observations": [],
                        "practical_steps": ["可以按自己的节奏查看支持资源。"],
                        "boundary_notice": "这段说明用于帮助你阅读固定结果，不是诊断或专业评估。",
                    },
                    ensure_ascii=False,
                ),
                model="fake-model",
            )

        async def aclose(self) -> None:
            pass

    service = AiAssistService(settings_for(), client=FallbackClient())
    result = await service.assessment_explanation(
        resource_id="result-1",
        owner_user_id="user-1",
        input_data=ASSESSMENT_INPUT,
    )

    assert result.status == "fallback"
    assert result.fallback_reason == "output_rejected"
    assert service.snapshots[result.snapshot_id or ""].output_status == "rejected"


async def test_ai_snapshot_persists_and_can_be_reloaded() -> None:
    repository = InMemoryDomainDataRepository()

    class StubClient(AIClient):
        async def complete(self, request: AIRequest) -> AIResponse:
            payload = json.loads(request.messages[-1].content)
            task_type = payload["task_type"]
            del payload
            return AIResponse(
                content=json.dumps(
                    {
                        "task_type": task_type,
                        "status": "ok",
                        "summary": (
                            "这段说明帮助你阅读已经完成的固定结果，并保持原有分层不变，"
                            "你可以按自己的节奏决定是否查看支持资源。"
                        ),
                        "observations": ["本次结果只作为自我观察参考。"],
                        "practical_steps": ["可以先查看支持资源。"],
                        "boundary_notice": "这段说明用于帮助你阅读固定结果，不是诊断或专业评估。",
                    },
                    ensure_ascii=False,
                ),
                model="fake-model",
            )

        async def aclose(self) -> None:
            pass

    first = AiAssistService(settings_for(), client=StubClient(), repository=repository)
    result = await first.assessment_explanation(
        resource_id="result-persistent",
        owner_user_id="user-1",
        input_data=ASSESSMENT_INPUT,
    )
    second = AiAssistService(settings_for(), client=StubClient(), repository=repository)

    projection = await second.snapshot_projection(result.snapshot_id)

    assert projection is not None
    assert projection["status"] == "adopted"
    assert projection["output_projection"]["task_type"] == "assessment_explanation"


async def test_snapshot_and_audit_rollback_together_without_leaving_cached_output() -> None:
    class FailingAudit(InMemoryAuditRepository):
        async def append(self, event: AuditEventRecord) -> AuditEventRecord:
            raise RepositoryUnavailable("test audit failure")

    repository = InMemoryDomainDataRepository()
    service = AiAssistService(
        settings_for(api_key=None),
        repository=repository,
        audit_writer=AuditWriter(FailingAudit()),
    )
    with pytest.raises(RepositoryUnavailable):
        await service.assessment_explanation(
            resource_id="result", owner_user_id="user", input_data=ASSESSMENT_INPUT
        )
    assert await repository.extra_collection("ai_assist_snapshots") == []
    assert service.snapshots == {}
    await service.aclose()
