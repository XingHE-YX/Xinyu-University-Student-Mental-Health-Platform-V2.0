"""Use-case orchestration for the two deliberately limited AI assists."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from app.infra.ai.client.abstract import AIClient
from app.infra.ai.client.factory import create_ai_client
from app.infra.ai.prompt.manager import PromptManager
from app.infra.ai.prompt.templates.common import (
    PROMPT_VERSION,
    REQUEST_MODEL,
    RESOLVED_MODEL_VERSION,
)
from app.infra.config.settings import Settings
from app.infra.logger.audit import AuditWriter
from app.infra.logger.common import get_logger, traced
from app.services.v2.repositories import DomainRepository
from app.services.v2.rules.ai_policy import (
    PolicyViolation,
    project_assessment_input,
    project_treehole_input,
    validate_ai_output,
)

TaskType = Literal["assessment_explanation", "treehole_review_assist"]
logger = get_logger(__name__)


class AIMetadata(TypedDict):
    request_model: str
    resolved_model_version: str
    prompt_version: str


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
        client: AIClient | None = None,
        prompts: PromptManager | None = None,
        audit_writer: AuditWriter | None = None,
        repository: DomainRepository | None = None,
    ) -> None:
        self.settings = settings
        self.prompts = prompts or PromptManager()
        self.client = client or create_ai_client(
            settings.ai,
            api_key=settings.deepseek_api_key.get_secret_value()
            if settings.deepseek_api_key
            else None,
        )
        self.audit = audit_writer or AuditWriter(
            environment_id=settings.cloudbase_env_id or settings.environment_kind.value
        )
        self.repository = repository
        self.snapshots: dict[str, AiAssistSnapshot] = {}

    @traced
    async def snapshot_projection(self, snapshot_id: str | None) -> dict[str, Any] | None:
        if not snapshot_id:
            return None
        snapshot = self.snapshots.get(snapshot_id) or (await self._load_snapshot(snapshot_id))
        if snapshot is None:
            return None
        return {
            "status": "adopted" if snapshot.output_status == "adopted" else "fallback",
            "output_projection": snapshot.output_projection,
            "fallback_copy": (
                "AI 辅助解读暂时不可用，当前使用固定规则说明"
                if snapshot.output_status != "adopted"
                else None
            ),
        }

    @traced
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
            return await self._fallback(
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

    @traced
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
            return await self._fallback(
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

    @traced
    async def assist_assessment(self, **kwargs: Any) -> AiAssistResult:
        return await self.assessment_explanation(**kwargs)

    @traced
    async def assist_treehole(self, **kwargs: Any) -> AiAssistResult:
        return await self.treehole_review_assist(**kwargs)

    @traced
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

    @traced
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
            response = await self.client.complete(
                self.prompts.request(task_type, projected, self.settings.ai)
            )
            raw = json.loads(response.content)
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
            return await self._fallback(
                task_type=task_type,
                resource_type=resource_type,
                resource_id=resource_id,
                owner_user_id=owner_user_id,
                input_data=projected,
                reason=reason,
                fixed_band=fixed_band,
            )
        return await self._adopt(
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_user_id=owner_user_id,
            projected=projected,
            output=output,
            fixed_band=fixed_band,
        )

    @traced
    async def _fallback(
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
        snapshot = await self._snapshot(
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_user_id=owner_user_id,
            input_data=input_data,
            output_status="rejected" if reason == "output_rejected" else "fallback",
            output_projection=None,
            adopted_copy=None,
        )
        (await self._audit(task_type, "fallback", reason))
        if task_type == "assessment_explanation":
            return AiAssistResult(
                **self._metadata(task_type),
                task_type=task_type,
                status="fallback",
                fallback_copy="AI 辅助解读暂时不可用，当前使用固定规则说明",
                fallback_reason="dependency_unavailable" if reason != "output_rejected" else reason,
                snapshot_id=snapshot.snapshot_id,
                fixed_band_unchanged=fixed_band,
            )
        return AiAssistResult(
            **self._metadata(task_type),
            task_type=task_type,
            status="fallback",
            fallback_copy="自动检查未完成，请进行人工处理",
            fallback_reason="dependency_unavailable" if reason != "output_rejected" else reason,
            snapshot_id=snapshot.snapshot_id,
            manual_review_required=True,
            recommended_route="manual_review",
            visibility_state="pending_confirmation",
        )

    @traced
    async def _adopt(
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
        snapshot = await self._snapshot(
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
            owner_user_id=owner_user_id,
            input_data=projected,
            output_status="adopted",
            output_projection=output,
            adopted_copy=adopted_copy if isinstance(adopted_copy, str) else None,
        )
        (await self._audit(task_type, "adopted", None))
        route = output.get("recommended_route") if task_type == "treehole_review_assist" else None
        return AiAssistResult(
            **self._metadata(task_type),
            task_type=task_type,
            status="adopted",
            output=output,
            snapshot_id=snapshot.snapshot_id,
            fixed_band_unchanged=fixed_band,
            recommended_route=route if isinstance(route, str) else None,
        )

    @traced
    async def _snapshot(
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
            **self._metadata(task_type),
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
        if self.repository is not None:
            try:
                document = snapshot.model_dump(mode="python")
                document["_id"] = document.pop("snapshot_id")
                (await self.repository.append_extra_document("ai_assist_snapshots", document))
            except Exception:
                logger.warning("ai_snapshot_write_failed")
        return snapshot

    @traced
    async def _load_snapshot(self, snapshot_id: str) -> AiAssistSnapshot | None:
        if self.repository is None:
            return None
        try:
            for document in await self.repository.extra_collection("ai_assist_snapshots"):
                if document.get("_id") != snapshot_id:
                    continue
                values = dict(document)
                values["snapshot_id"] = values.pop("_id")
                snapshot = AiAssistSnapshot.model_validate(values)
                self.snapshots[snapshot.snapshot_id] = snapshot
                return snapshot
        except Exception:
            logger.warning("ai_snapshot_read_failed")
        return None

    @traced
    async def _audit(self, task_type: TaskType, outcome: str, reason: str | None) -> None:
        (
            await self.audit.write(
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
                    "model_version": self.settings.ai.resolved_model_version,
                    "prompt_version": self.prompts.get(task_type).version,
                    "outcome_category": outcome,
                    "error_category": reason,
                },
            )
        )

    @traced
    def _metadata(self, task_type: str) -> AIMetadata:
        return {
            "request_model": self.settings.ai.model,
            "resolved_model_version": self.settings.ai.resolved_model_version,
            "prompt_version": self.prompts.get(task_type).version,
        }

    @traced
    async def aclose(self) -> None:
        await self.client.aclose()

    @staticmethod
    @traced
    def _project_assessment(data: Mapping[str, Any]) -> dict[str, Any] | None:
        try:
            return project_assessment_input(data)
        except PolicyViolation:
            return None

    @staticmethod
    @traced
    def _project_treehole(data: Mapping[str, Any]) -> dict[str, Any] | None:
        try:
            return project_treehole_input(data)
        except PolicyViolation:
            return None
