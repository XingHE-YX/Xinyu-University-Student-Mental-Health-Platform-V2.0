"""Deterministic safety branch rules for PHQ-9 question 9."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SafetyConfirmationState = Literal["can_be_safe", "uncertain", "cannot_be_safe"]
SafetyNextStep = Literal["continue_assessment", "show_support_resources", "support_only"]

SAFETY_CONFIRMATION_QUESTION = (
    "刚才的回答涉及过去两周的感受。我想再确认一下你此刻的状态：现在，你能保证自己是安全的吗？"
)
SAFETY_CONFIRMATION_OPTIONS = {
    "can_be_safe": "我现在可以保证安全",
    "uncertain": "我不太确定",
    "cannot_be_safe": "我现在无法保证安全",
}
SAFETY_CONFIRMATION_SOURCE = "phq9_current_safety_confirmation"


@dataclass(frozen=True, slots=True)
class SafetyBranchDecision:
    next_step: SafetyNextStep
    support_required: bool
    creates_immediate_task: bool


def decide_safety_branch(state: SafetyConfirmationState) -> SafetyBranchDecision:
    if state == "can_be_safe":
        return SafetyBranchDecision(
            next_step="continue_assessment",
            support_required=False,
            creates_immediate_task=False,
        )
    if state == "uncertain":
        return SafetyBranchDecision(
            next_step="show_support_resources",
            support_required=True,
            creates_immediate_task=False,
        )
    return SafetyBranchDecision(
        next_step="support_only",
        support_required=True,
        creates_immediate_task=True,
    )


def minimal_visible_projection(
    *,
    state: SafetyConfirmationState,
    resource_categories_shown: list[str],
    questionnaire_completed: bool,
    task_state: str | None,
) -> dict[str, object]:
    return {
        "confirmation_source": SAFETY_CONFIRMATION_SOURCE,
        "current_selection": state,
        "resource_categories_shown": resource_categories_shown,
        "questionnaire_completed": questionnaire_completed,
        "task_state": task_state,
    }
