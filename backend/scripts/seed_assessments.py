"""Deterministic frozen assessment seed bundle."""

from __future__ import annotations

import json
from typing import Any

from app.config.environments import EnvironmentKind
from app.domain.assessment_rules import SCORING_RULE_VERSION, build_seed_documents
from app.domain.models import AssessmentModuleDocument, AssessmentQuestionnaireDocument


def build_assessment_seed_bundle(
    *,
    environment_kind: EnvironmentKind,
    include_demo_records: bool,
) -> dict[str, Any]:
    if include_demo_records and environment_kind is not EnvironmentKind.DEMO:
        raise ValueError("demo assessment records can only be generated for demo environments")

    seed_documents = build_seed_documents()
    modules = [
        AssessmentModuleDocument.model_validate(item).model_dump(mode="json", by_alias=True)
        for item in seed_documents["assessment_modules"]
    ]
    questionnaires = [
        AssessmentQuestionnaireDocument.model_validate(item).model_dump(mode="json", by_alias=True)
        for item in seed_documents["assessment_questionnaires"]
    ]
    return {
        "generated_at": modules[0]["created_at"],
        "scoring_rule_version": SCORING_RULE_VERSION,
        "collections": {
            "assessment_modules": modules,
            "assessment_questionnaires": questionnaires,
        },
    }


def main() -> int:
    print(
        json.dumps(
            build_assessment_seed_bundle(
                environment_kind=EnvironmentKind.AUTHORIZED,
                include_demo_records=False,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0
