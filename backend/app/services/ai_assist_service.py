"""Use-case orchestration for the two deliberately limited AI assists."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from app.audit.writer import AuditWriter
from app.config.ai_prompt import PROMPT_VERSION, REQUEST_MODEL, RESOLVED_MODEL_VERSION
from app.config.settings import Settings
from app.domain.ai_policy import (
    PolicyViolation,
    project_assessment_input,
    project_treehole_input,
    validate_ai_output,
)
from app.integrations.deepseek_client import DeepSeekClient

TaskType = Literal["assessment_explanation", "treehole_review_assist"]


class AiClient(Protocol):
    async def complete(self, *, task_type: str, payload: Mapping[str, Any]) -> dict[str, Any]: ...


class AiAssistResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: TaskType
    status: Literal["adopted", "fallback"]
    output: dict[str, Any] | None = None
    fallback_copy: str | None = None
    fallback_reason: str | None = None
    snapshot_id: str | None = None
    fixed_result_available: bool = True
    fixed_band_unchanged: str | None = None
    manual_review_required: bool = False
    recommended_route: str | None = None
    visibility_state: str | None = None
    request_model: str = REQUEST_MODEL
    resolved_model_version: str = RESOLVED_MODEL_VERSION
    prompt_version: str = PROMPT_VERSION


class AiAssistSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    task_type: TaskType
    resource_type: Literal["assessment_result", "treehole_post", "treehole_response"]
    resource_id: str
    owner_user_id: str | None = None
    input_digest: str
    request_model: str = REQUEST_MODEL
    resolved_model_version: str = RESOLVED_MODEL_VERSION
    prompt_version: str = PROMPT_VERSION
    output_status: Literal["adopted", "fallback", "rejected"]
    output_projection: dict[str, Any] | None = None
    adopted_copy: str | None = None
    created_at: datetime
    updated_at: datetime
    version: int = 1


class AiAssistService:
    def __init__(
        self,
        settings: Settings,
        *,
        client: AiClient | None = None,
        audit_writer: AuditWriter | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or DeepSeekClient(
            api_key=settings.deepseek_api_key.get_secret_value()
            if settings.deepseek_api_key
            else None
        )
        self.audit = audit_writer or AuditWriter(
            environment_id=settings.cloudbase_env_id or settings.environment_kind.value
        )
        self.snapshots: dict[str, AiAssistSnapshot] = {}

    async def assessment_explanation(
        self,
        *,
        resource_id: str,
        owner_user_id: str | None,
        input_data: Mapping[str, Any],
    ) -> AiAssistResult:
        projected = self._project_assessment(input_data)
        fixed_band_value = input_data.get("fixed_band")
        fixed_band = fixed_band_value if isinstance(fixed_band_value, str) else None
        if projected is None:
            return self._fallback(
                task_type="assessment_explanation",
                resource_type="assessment_result",
                resource_id=resource_id,
                owner_user_id=owner_user_id,
                input_data=input_data,
                reason="policy_input_rejected",
                fixed_band=fixed_band,
            )
        return await self._run(
            task_type="assessment_explanation",
            resource_type="assessment_result",
            resource_id=resource_id,
            owner_user_id=owner_user_id,
            projected=projected,
            fixed_band=str(projected["fixed_band"]),
        )

    async def treehole_review_assist(
        self,
        *,
        resource_id: str,
        input_data: Mapping[str, Any],
        owner_user_id: str | None = None,
    ) -> AiAssistResult:
        projected = self._project_treehole(input_data)
        resource_type: Literal["treehole_post", "treehole_response"] = (
            "treehole_response" if input_data.get("content_type") == "response" else "treehole_post"
        )
        if projected is None:
            return self._fallback(
                task_type="treehole_review_assist",
                resource_type=resource_type,
                resource_id=resource_id,
                owner_user_id=owner_user_id,
                input_data=input_data,
                reason="policy_input_rejected",
            )
        return await self._run(
            task_type="treehole_review_assist",
            resource_type=resource_type,
            resource_id=resource_id,
            owner_user_id=owner_user_id,
            projected=projected,
        )

    async def assist_assessment(self, **kwargs: Any) -> AiAssistResult:
        return await self.assessment_explanation(**kwargs)

    async def assist_treehole(self, **kwargs: Any) -> AiAssistResult:
        return await self.treehole_review_assist(**kwargs)

    async def run(
        self,
        task_type: TaskType,
        *,
        resource_id: str,
        input_data: Mapping[str, Any],
        owner_user_id: str | None = None,
    ) -> AiAssistResult:
        if task_type == "assessment_explanation":
            return await self.assessment_explanation(
                resource_id=resource_id,
                owner_user_id=owner_user_id,
                input_data=input_data,
            )
        return await self.treehole_review_assist(
            resource_id=resource_id,
            owner_user_id=owner_user_id,
            input_data=input_data,
        )

    async def _run(
        self,
        *,
        task_type: TaskType,
        resource_type: Literal["assessment_result", "treehole_post", "treehole_response"],
        resource_id: str,
        owner_user_id: str | None,
        projected: dict[str, Any],
        fixed_band: str | None = None,
    ) -> AiAssistResult:
        try:
            raw = await self.client.complete(task_type=task_type, payload=projected)
            output = validate_ai_output(
                task_type,
                raw,
                source_text=projected.get("sanitized_text"),
                content_type=projected.get("content_type"),
            )
            if output.get("status") == "needs_fallback":
                raise PolicyViolation("AI 请求主动要求回退")
        except Exception as error:
            reason = (
                "output_rejected"
                if isinstance(error, PolicyViolation)
                else "dependency_unavailable"
            )
            return self._fallback(
                task_type=task_type,
                resource_type=resource_type,
                resource_id=resource_id,
                owner_user_id=owner_user_id,
                input_data=projected,
                reason=reason,
                fixed_band=fixed_band,
            )
        return self._adopt(
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_user_id=owner_user_id,
            projected=projected,
            output=output,
            fixed_band=fixed_band,
        )

    def _fallback(
        self,
        *,
        task_type: TaskType,
        resource_type: Literal["assessment_result", "treehole_post", "treehole_response"],
        resource_id: str,
        owner_user_id: str | None,
        input_data: Mapping[str, Any],
        reason: str,
        fixed_band: str | None = None,
    ) -> AiAssistResult:
        snapshot = self._snapshot(
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_user_id=owner_user_id,
            input_data=input_data,
            output_status="rejected" if reason == "output_rejected" else "fallback",
            output_projection=None,
            adopted_copy=None,
        )
        self._audit(task_type, "fallback", reason)
        if task_type == "assessment_explanation":
            return AiAssistResult(
                task_type=task_type,
                status="fallback",
                fallback_copy="AI 辅助解读暂时不可用，当前使用固定规则说明",
                fallback_reason="dependency_unavailable" if reason != "output_rejected" else reason,
                snapshot_id=snapshot.snapshot_id,
                fixed_band_unchanged=fixed_band,
            )
        return AiAssistResult(
            task_type=task_type,
            status="fallback",
            fallback_copy="自动检查未完成，请进行人工处理",
            fallback_reason="dependency_unavailable" if reason != "output_rejected" else reason,
            snapshot_id=snapshot.snapshot_id,
            manual_review_required=True,
            recommended_route="manual_review",
            visibility_state="pending_confirmation",
        )

    def _adopt(
        self,
        *,
        task_type: TaskType,
        resource_type: Literal["assessment_result", "treehole_post", "treehole_response"],
        resource_id: str,
        owner_user_id: str | None,
        projected: dict[str, Any],
        output: dict[str, Any],
        fixed_band: str | None,
    ) -> AiAssistResult:
        adopted_copy = (
            output.get("summary")
            if task_type == "assessment_explanation"
            else output.get("review_note")
        )
        snapshot = self._snapshot(
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_user_id=owner_user_id,
            input_data=projected,
            output_status="adopted",
            output_projection=output,
            adopted_copy=adopted_copy if isinstance(adopted_copy, str) else None,
        )
        self._audit(task_type, "adopted", None)
        route = output.get("recommended_route") if task_type == "treehole_review_assist" else None
        return AiAssistResult(
            task_type=task_type,
            status="adopted",
            output=output,
            snapshot_id=snapshot.snapshot_id,
            fixed_band_unchanged=fixed_band,
            recommended_route=route if isinstance(route, str) else None,
        )

    def _snapshot(
        self,
        *,
        task_type: TaskType,
        resource_type: Literal["assessment_result", "treehole_post", "treehole_response"],
        resource_id: str,
        owner_user_id: str | None,
        input_data: Mapping[str, Any],
        output_status: Literal["adopted", "fallback", "rejected"],
        output_projection: dict[str, Any] | None,
        adopted_copy: str | None,
    ) -> AiAssistSnapshot:
        now = datetime.now(UTC)
        snapshot = AiAssistSnapshot(
            snapshot_id=f"ai_{uuid4().hex}",
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_user_id=owner_user_id,
            input_digest=hashlib.sha256(
                json.dumps(dict(input_data), ensure_ascii=False, sort_keys=True).encode()
            ).hexdigest(),
            output_status=output_status,
            output_projection=output_projection,
            adopted_copy=adopted_copy,
            created_at=now,
            updated_at=now,
        )
        self.snapshots[snapshot.snapshot_id] = snapshot
        return snapshot

    def _audit(self, task_type: TaskType, outcome: str, reason: str | None) -> None:
        self.audit.write(
            request_id=f"ai_{uuid4().hex}",
            actor_type="system",
            actor_id="ai-assist",
            capability="restricted_ai",
            action="ai_assist",
            resource_type="ai_assist",
            resource_id=task_type,
            data_scope="task_type,model_version,prompt_version,outcome_category,error_category",
            outcome="success" if outcome == "adopted" else "failure",
            reason_code=reason,
            occurred_at=datetime.now(UTC),
            facts={
                "task_kind": task_type,
                "model_version": RESOLVED_MODEL_VERSION,
                "prompt_version": PROMPT_VERSION,
                "outcome_category": outcome,
                "error_category": reason,
            },
        )

    @staticmethod
    def _project_assessment(data: Mapping[str, Any]) -> dict[str, Any] | None:
        try:
            return project_assessment_input(data)
        except PolicyViolation:
            return None

    @staticmethod
    def _project_treehole(data: Mapping[str, Any]) -> dict[str, Any] | None:
        try:
            return project_treehole_input(data)
        except PolicyViolation:
            return None
