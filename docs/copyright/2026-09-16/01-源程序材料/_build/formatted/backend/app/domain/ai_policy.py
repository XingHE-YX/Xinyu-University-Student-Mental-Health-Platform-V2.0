"""Deterministic input/output policy for restricted AI assistance."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.config.ai_prompt import PROMPT_VERSION, REQUEST_MODEL, RESOLVED_MODEL_VERSION

ALLOWED_TASK_TYPES = {"assessment_explanation", "treehole_review_assist"}
ASSESSMENT_FIELDS = {
    "task_type",
    "module",
    "score",
    "max_score",
    "fixed_band",
    "fixed_summary",
    "derived_facts",
    "allowed_steps",
}
TREEHOLE_FIELDS = {
    "task_type",
    "content_type",
    "topic",
    "sanitized_text",
    "rule_flags",
    "protect_supported",
}
ASSESSMENT_OUTPUT_FIELDS = {
    "task_type",
    "status",
    "summary",
    "observations",
    "practical_steps",
    "boundary_notice",
}
TREEHOLE_OUTPUT_FIELDS = {
    "task_type",
    "status",
    "content_safety",
    "wellbeing_signal",
    "privacy_signal",
    "community_issue",
    "evidence_spans",
    "recommended_route",
    "review_note",
}
BOUNDARY_NOTICE = "这段说明用于帮助你阅读固定结果，不是诊断或专业评估。"
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{6,}\d)(?!\d)")
_IDENTITY_MARKERS = ("姓名", "学号", "手机号", "身份证", "openid", "unionid", "联系方式")
_AI_PROHIBITED = ("诊断", "治疗", "药物", "自伤风险", "危机等级", "高危", "低危", "思维链")


class PolicyViolation(ValueError):
    """Raised when an AI input or output crosses the frozen policy boundary."""


def project_assessment_input(data: Mapping[str, Any]) -> dict[str, Any]:
    _require_task(data, "assessment_explanation")
    if any(
        key in data
        for key in {"safety_confirmation", "safety_state", "risk_question", "risk_level"}
    ):
        raise PolicyViolation("自测辅助输入不能包含安全确认或风险判断字段")
    required = {
        "module",
        "score",
        "max_score",
        "fixed_band",
        "fixed_summary",
        "derived_facts",
        "allowed_steps",
    }
    if not required.issubset(data):
        raise PolicyViolation("自测辅助输入字段不完整")
    if data["module"] not in {"PHQ9", "GAD7"}:
        raise PolicyViolation("自测辅助仅支持 PHQ9 或 GAD7")
    if (
        not isinstance(data["score"], int)
        or isinstance(data["score"], bool)
        or not isinstance(data["max_score"], int)
        or isinstance(data["max_score"], bool)
    ):
        raise PolicyViolation("分数字段格式不正确")
    if not 0 <= data["score"] <= data["max_score"] or data["max_score"] <= 0:
        raise PolicyViolation("分数范围不正确")
    _require_string(data, "fixed_band", 200)
    _require_string(data, "fixed_summary", 500)
    _require_string_list(data, "derived_facts", maximum=8, item_max=100)
    _require_string_list(data, "allowed_steps", minimum=1, maximum=3, item_max=100)
    for value in [
        data["fixed_band"],
        data["fixed_summary"],
        *data["derived_facts"],
        *data["allowed_steps"],
    ]:
        _reject_sensitive_text(value)
        _reject_prohibited_text(value)
    return _copy_json_fields(data, ASSESSMENT_FIELDS)


def project_treehole_input(data: Mapping[str, Any]) -> dict[str, Any]:
    _require_task(data, "treehole_review_assist")
    if not TREEHOLE_FIELDS.issubset(data):
        raise PolicyViolation("树洞辅助输入字段不完整")
    if data["content_type"] not in {"post", "response"}:
        raise PolicyViolation("树洞内容类型不正确")
    _require_string(data, "topic", 80)
    text = _require_string(data, "sanitized_text", 2000)
    if not text.strip() or _PHONE_PATTERN.search(text):
        raise PolicyViolation("树洞输入必须先完成脱敏")
    _require_string_list(data, "rule_flags", maximum=12, item_max=80)
    if not isinstance(data["protect_supported"], bool):
        raise PolicyViolation("保护展示能力字段格式不正确")
    return _copy_json_fields(data, TREEHOLE_FIELDS)


def validate_ai_output(
    task_type: str,
    output: Mapping[str, Any],
    *,
    source_text: str | None = None,
    content_type: str | None = None,
) -> dict[str, Any]:
    if task_type not in ALLOWED_TASK_TYPES or not isinstance(output, Mapping):
        raise PolicyViolation("AI 输出任务类型不正确")
    allowed = (
        ASSESSMENT_OUTPUT_FIELDS
        if task_type == "assessment_explanation"
        else TREEHOLE_OUTPUT_FIELDS
    )
    _reject_unknown(output, allowed)
    if task_type == "assessment_explanation":
        required = ASSESSMENT_OUTPUT_FIELDS
        if set(output) != required or output.get("task_type") != task_type:
            raise PolicyViolation("自测辅助输出结构不正确")
        if output.get("status") not in {"ok", "needs_fallback"}:
            raise PolicyViolation("自测辅助输出状态不正确")
        summary = _require_string(output, "summary", 240)
        if not 40 <= len(summary) <= 90:
            raise PolicyViolation("自测辅助摘要长度不正确")
        _require_string_list(output, "observations", maximum=3, item_max=100)
        _require_string_list(output, "practical_steps", minimum=1, maximum=3, item_max=120)
        if output.get("boundary_notice") != BOUNDARY_NOTICE:
            raise PolicyViolation("自测辅助必须包含固定边界提醒")
        for value in [output["summary"], *output["observations"], *output["practical_steps"]]:
            _reject_sensitive_text(value)
            _reject_prohibited_text(value)
    else:
        required = TREEHOLE_OUTPUT_FIELDS
        if set(output) != required or output.get("task_type") != task_type:
            raise PolicyViolation("树洞辅助输出结构不正确")
        if output.get("status") not in {"ok", "needs_fallback"}:
            raise PolicyViolation("树洞辅助输出状态不正确")
        if output.get("content_safety") not in {
            "clear",
            "possible_issue",
            "clear_issue",
            "unknown",
        }:
            raise PolicyViolation("内容安全枚举不正确")
        if output.get("wellbeing_signal") not in {
            "none",
            "supportive_attention",
            "manual_attention",
            "unknown",
        }:
            raise PolicyViolation("支持信号枚举不正确")
        if output.get("privacy_signal") not in {"clear", "possible_residual", "unknown"}:
            raise PolicyViolation("隐私信号枚举不正确")
        issues = output.get("community_issue")
        if not isinstance(issues, list) or not 1 <= len(issues) <= 6:
            raise PolicyViolation("社区问题字段不正确")
        issue_values = {
            "harassment",
            "sexual_content",
            "violence",
            "illegal_content",
            "spam",
            "none",
            "unknown",
        }
        if any(item not in issue_values for item in issues):
            raise PolicyViolation("社区问题枚举不正确")
        spans = output.get("evidence_spans")
        if (
            not isinstance(spans, list)
            or len(spans) > 3
            or any(not isinstance(item, str) or len(item) > 120 for item in spans)
        ):
            raise PolicyViolation("证据片段字段不正确")
        if source_text is None:
            raise PolicyViolation("缺少脱敏原文用于证据校验")
        if any(span not in source_text or "［已隐藏" in span for span in spans):
            raise PolicyViolation("证据片段必须来自脱敏文本")
        route = output.get("recommended_route")
        if route not in {"allow", "protect", "manual_review", "safety_review"}:
            raise PolicyViolation("推荐路径枚举不正确")
        if content_type == "response" and route == "protect":
            raise PolicyViolation("回应不得推荐保护展示")
        _require_string(output, "review_note", 240)
        _reject_sensitive_text(output["review_note"])
        _reject_prohibited_text(output["review_note"])
    return dict(output)


def _require_task(data: Mapping[str, Any], task_type: str) -> None:
    if data.get("task_type") != task_type:
        raise PolicyViolation("AI 任务类型不在允许范围")


def _reject_unknown(data: Mapping[str, Any], allowed: set[str]) -> None:
    unknown = set(data) - allowed
    if unknown:
        raise PolicyViolation("AI 输入或输出包含未允许字段")


def _require_string(data: Mapping[str, Any], key: str, maximum: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or len(value) > maximum:
        raise PolicyViolation(f"字段 {key} 格式不正确")
    return value


def _require_string_list(
    data: Mapping[str, Any], key: str, *, minimum: int = 0, maximum: int, item_max: int
) -> None:
    value = data.get(key)
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise PolicyViolation(f"字段 {key} 格式不正确")
    if any(not isinstance(item, str) or len(item) > item_max for item in value):
        raise PolicyViolation(f"字段 {key} 格式不正确")


def _reject_sensitive_text(value: str) -> None:
    if _PHONE_PATTERN.search(value) or any(
        marker.lower() in value.lower() for marker in _IDENTITY_MARKERS
    ):
        raise PolicyViolation("文本包含身份或联系方式")


def _reject_prohibited_text(value: str) -> None:
    if any(marker in value for marker in _AI_PROHIBITED):
        raise PolicyViolation("AI 输出包含受限内容")


def _copy_json_fields(data: Mapping[str, Any], fields: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in fields:
        value = data[key]
        result[key] = list(value) if isinstance(value, list) else value
    return result


def ai_metadata() -> dict[str, str]:
    return {
        "request_model": REQUEST_MODEL,
        "resolved_model_version": RESOLVED_MODEL_VERSION,
        "prompt_version": PROMPT_VERSION,
    }
