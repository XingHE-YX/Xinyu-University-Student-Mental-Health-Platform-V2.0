from __future__ import annotations

import importlib
import importlib.util
import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.config.environments import EnvironmentKind
from app.domain.models import (
    AssessmentModuleDocument,
    AssessmentQuestionnaireDocument,
)


def load_module(module_name: str) -> Any:
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, f"{module_name} module is missing"
    return importlib.import_module(module_name)


def test_fixed_assessment_catalog_matches_frozen_spec() -> None:
    rules = load_module("app.domain.assessment_rules")

    modules = rules.build_seed_documents()["assessment_modules"]
    questionnaires = rules.build_seed_documents()["assessment_questionnaires"]

    assert [module.module_code for module in modules] == ["phq9", "gad7", "sleep_observation"]
    assert [questionnaire.module_code for questionnaire in questionnaires] == [
        "phq9",
        "gad7",
        "sleep_observation",
    ]

    phq9 = next(item for item in questionnaires if item.module_code == "phq9")
    gad7 = next(item for item in questionnaires if item.module_code == "gad7")
    sleep = next(item for item in questionnaires if item.module_code == "sleep_observation")

    assert phq9.questionnaire_version == "phq9-cn-v1"
    assert len(phq9.questions) == 10
    assert [option.label for option in phq9.questions[0].options] == [
        "从来没有",
        "有几天",
        "超过一半天数",
        "接近每天",
    ]
    assert [option.score for option in phq9.questions[0].options] == [0, 1, 2, 3]
    assert phq9.questions[8].text == "想到自己最好去死或者自残。"
    assert phq9.questions[9].text == "这些问题对你的学习、日常事务或与人相处造成多大困难？"
    assert [option.score for option in phq9.questions[9].options] == [0, 0, 0, 0]

    assert gad7.questionnaire_version == "gad7-cn-v1"
    assert len(gad7.questions) == 7
    assert gad7.questions[0].text == "感觉心神不安、焦虑或高度紧张。"
    assert gad7.questions[6].text == "害怕发生可怕的事情。"

    assert sleep.questionnaire_version == "sleep-observation-v1"
    assert len(sleep.questions) == 8
    assert [option.label for option in sleep.questions[1].options] == [
        "少于 5 小时",
        "5–不足 6 小时",
        "6–不足 7 小时",
        "7–9 小时",
        "超过 9 小时",
    ]
    assert [option.label for option in sleep.questions[7].options] == [
        "还不困，作息已经乱了",
        "想把属于自己的时间再延长一点",
        "刷手机、追剧、游戏等停不下来",
        "学习、工作或其他事情还没完成",
        "脑子停不下来，反复想事情",
        "不太想面对明天",
        "环境、噪音或室友作息影响",
        "身体不舒服",
        "说不清",
        "不想回答",
    ]
    assert rules.SLEEP_Q8_REFUSAL_OPTION_KEY == "prefer_not_to_answer"


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        (
            [
                ("q1", "0"),
                ("q2", "0"),
                ("q3", "0"),
                ("q4", "0"),
                ("q5", "0"),
                ("q6", "0"),
                ("q7", "0"),
                ("q8", "0"),
                ("q9", "0"),
                ("impact", "very"),
            ],
            {
                "score": 0,
                "reference_band": "0-4",
                "result_state": "ordinary",
                "safety_triggered": False,
            },
        ),
        (
            [
                ("q1", "1"),
                ("q2", "1"),
                ("q3", "1"),
                ("q4", "1"),
                ("q5", "1"),
                ("q6", "0"),
                ("q7", "0"),
                ("q8", "0"),
                ("q9", "0"),
                ("impact", "some"),
            ],
            {
                "score": 5,
                "reference_band": "5-9",
                "result_state": "ordinary",
                "safety_triggered": False,
            },
        ),
        (
            [
                ("q1", "2"),
                ("q2", "2"),
                ("q3", "2"),
                ("q4", "2"),
                ("q5", "2"),
                ("q6", "0"),
                ("q7", "0"),
                ("q8", "0"),
                ("q9", "0"),
                ("impact", "very"),
            ],
            {
                "score": 10,
                "reference_band": "10-14",
                "result_state": "higher_score",
                "safety_triggered": False,
            },
        ),
        (
            [
                ("q1", "3"),
                ("q2", "3"),
                ("q3", "3"),
                ("q4", "3"),
                ("q5", "3"),
                ("q6", "0"),
                ("q7", "0"),
                ("q8", "0"),
                ("q9", "0"),
                ("impact", "extreme"),
            ],
            {
                "score": 15,
                "reference_band": "15-19",
                "result_state": "higher_score",
                "safety_triggered": False,
            },
        ),
        (
            [
                ("q1", "3"),
                ("q2", "3"),
                ("q3", "3"),
                ("q4", "3"),
                ("q5", "3"),
                ("q6", "3"),
                ("q7", "3"),
                ("q8", "1"),
                ("q9", "1"),
                ("impact", "extreme"),
            ],
            {
                "score": 23,
                "reference_band": "20-27",
                "result_state": "higher_score",
                "safety_triggered": True,
            },
        ),
    ],
)
def test_phq9_scoring_boundaries_and_impact_question_exclusion(
    answers: list[tuple[str, str]],
    expected: dict[str, object],
) -> None:
    rules = load_module("app.domain.assessment_rules")

    outcome = rules.score_questionnaire("phq9", answers)

    assert outcome.score == expected["score"]
    assert outcome.reference_band == expected["reference_band"]
    assert outcome.result_state == expected["result_state"]
    assert outcome.safety_triggered is expected["safety_triggered"]


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        (
            [
                ("q1", "0"),
                ("q2", "0"),
                ("q3", "0"),
                ("q4", "0"),
                ("q5", "0"),
                ("q6", "0"),
                ("q7", "0"),
            ],
            {"score": 0, "reference_band": "0-4", "result_state": "ordinary"},
        ),
        (
            [
                ("q1", "1"),
                ("q2", "1"),
                ("q3", "1"),
                ("q4", "1"),
                ("q5", "1"),
                ("q6", "0"),
                ("q7", "0"),
            ],
            {"score": 5, "reference_band": "5-9", "result_state": "ordinary"},
        ),
        (
            [
                ("q1", "2"),
                ("q2", "2"),
                ("q3", "2"),
                ("q4", "2"),
                ("q5", "2"),
                ("q6", "0"),
                ("q7", "0"),
            ],
            {"score": 10, "reference_band": "10-14", "result_state": "higher_score"},
        ),
        (
            [
                ("q1", "3"),
                ("q2", "3"),
                ("q3", "3"),
                ("q4", "3"),
                ("q5", "3"),
                ("q6", "0"),
                ("q7", "0"),
            ],
            {"score": 15, "reference_band": "15-21", "result_state": "higher_score"},
        ),
    ],
)
def test_gad7_scoring_boundaries(
    answers: list[tuple[str, str]], expected: dict[str, object]
) -> None:
    rules = load_module("app.domain.assessment_rules")

    outcome = rules.score_questionnaire("gad7", answers)

    assert outcome.score == expected["score"]
    assert outcome.reference_band == expected["reference_band"]
    assert outcome.result_state == expected["result_state"]
    assert outcome.safety_triggered is False


@pytest.mark.parametrize(
    ("module_code", "answers", "expected_summary"),
    [
        (
            "phq9",
            [
                ("q1", "0"),
                ("q2", "0"),
                ("q3", "0"),
                ("q4", "0"),
                ("q5", "0"),
                ("q6", "0"),
                ("q7", "0"),
                ("q8", "0"),
                ("q9", "0"),
                ("impact", "none"),
            ],
            "这次记录里，近期情绪相关信号较少。",
        ),
        (
            "phq9",
            [
                ("q1", "1"),
                ("q2", "1"),
                ("q3", "1"),
                ("q4", "1"),
                ("q5", "1"),
                ("q6", "0"),
                ("q7", "0"),
                ("q8", "0"),
                ("q9", "0"),
                ("impact", "some"),
            ],
            "这次记录显示，你近期有一些情绪困扰。",
        ),
        (
            "phq9",
            [
                ("q1", "2"),
                ("q2", "2"),
                ("q3", "2"),
                ("q4", "2"),
                ("q5", "2"),
                ("q6", "0"),
                ("q7", "0"),
                ("q8", "0"),
                ("q9", "0"),
                ("impact", "very"),
            ],
            "这次记录显示，你近期的情绪困扰比较明显。",
        ),
        (
            "phq9",
            [
                ("q1", "3"),
                ("q2", "3"),
                ("q3", "3"),
                ("q4", "3"),
                ("q5", "3"),
                ("q6", "0"),
                ("q7", "0"),
                ("q8", "0"),
                ("q9", "0"),
                ("impact", "extreme"),
            ],
            "这次记录显示，你近期的情绪困扰较重。",
        ),
        (
            "phq9",
            [
                ("q1", "3"),
                ("q2", "3"),
                ("q3", "3"),
                ("q4", "3"),
                ("q5", "3"),
                ("q6", "3"),
                ("q7", "2"),
                ("q8", "0"),
                ("q9", "0"),
                ("impact", "extreme"),
            ],
            "这次记录显示，你近期的情绪困扰较多，值得尽快获得支持。",
        ),
        (
            "gad7",
            [
                ("q1", "0"),
                ("q2", "0"),
                ("q3", "0"),
                ("q4", "0"),
                ("q5", "0"),
                ("q6", "0"),
                ("q7", "0"),
            ],
            "这次记录里，近期紧绷和担心的信号较少。",
        ),
        (
            "gad7",
            [
                ("q1", "1"),
                ("q2", "1"),
                ("q3", "1"),
                ("q4", "1"),
                ("q5", "1"),
                ("q6", "0"),
                ("q7", "0"),
            ],
            "这次记录显示，你近期有一些紧绷或担心。",
        ),
        (
            "gad7",
            [
                ("q1", "2"),
                ("q2", "2"),
                ("q3", "2"),
                ("q4", "2"),
                ("q5", "2"),
                ("q6", "0"),
                ("q7", "0"),
            ],
            "这次记录显示，你近期焦虑相关的困扰比较明显。",
        ),
        (
            "gad7",
            [
                ("q1", "3"),
                ("q2", "3"),
                ("q3", "3"),
                ("q4", "3"),
                ("q5", "3"),
                ("q6", "0"),
                ("q7", "0"),
            ],
            "这次记录显示，你近期的焦虑相关困扰较重，值得尽快与专业人员交流。",
        ),
    ],
)
def test_fixed_standard_result_copy_matches_the_frozen_design(
    module_code: str,
    answers: list[tuple[str, str]],
    expected_summary: str,
) -> None:
    rules = load_module("app.domain.assessment_rules")

    outcome = rules.score_questionnaire(module_code, answers)

    assert outcome.fixed_summary == expected_summary
    assert outcome.boundary_notice == "这是一项筛查结果，用于自我观察，不构成诊断。"


def test_sleep_observation_returns_three_dimensions_without_total_score() -> None:
    rules = load_module("app.domain.assessment_rules")

    outcome = rules.score_questionnaire(
        "sleep_observation",
        [
            ("q1", "large_variation"),
            ("q2", "7_to_9"),
            ("q3", "over_60"),
            ("q4", "hard_to_sleep_again"),
            ("q5", "very_tired"),
            ("q6", "major_impact"),
            ("q7", "almost_daily"),
            ("q8", "extend_personal_time"),
            ("q8", "overthinking"),
        ],
    )

    assert outcome.score is None
    assert outcome.reference_band is None
    assert outcome.result_state == "ordinary"
    assert outcome.dimension_summary == {
        "rhythm": "波动很明显",
        "duration_fact": "你记录的大多数夜晚实际睡眠约为 7–9 小时",
        "bedtime_resistance": "经常出现",
        "bedtime_reasons": ["想把属于自己的时间再延长一点", "脑子停不下来，反复想事情"],
        "recovery_daytime_impact": "影响较明显",
    }
    assert outcome.fixed_summary == "这次记录帮助你看见最近 7 天的睡眠、作息和白天恢复状态。"


def test_sleep_question_8_refusal_is_mutually_exclusive() -> None:
    rules = load_module("app.domain.assessment_rules")

    with pytest.raises(rules.AssessmentValidationError) as error:
        rules.score_questionnaire(
            "sleep_observation",
            [
                ("q1", "stable"),
                ("q2", "under_5"),
                ("q3", "within_15"),
                ("q4", "easy_to_resume"),
                ("q5", "good"),
                ("q6", "none"),
                ("q7", "never"),
                ("q8", "prefer_not_to_answer"),
                ("q8", "unclear"),
            ],
        )

    assert error.value.code == "VALIDATION_FAILED"


def test_seed_assessments_is_deterministic_and_safe() -> None:
    seed_assessments = load_module("scripts.seed_assessments")

    with pytest.raises(ValueError):
        seed_assessments.build_assessment_seed_bundle(
            environment_kind=EnvironmentKind.AUTHORIZED,
            include_demo_records=True,
        )

    first_bundle = seed_assessments.build_assessment_seed_bundle(
        environment_kind=EnvironmentKind.AUTHORIZED,
        include_demo_records=False,
    )
    second_bundle = seed_assessments.build_assessment_seed_bundle(
        environment_kind=EnvironmentKind.AUTHORIZED,
        include_demo_records=False,
    )

    assert first_bundle == second_bundle
    json.dumps(first_bundle, ensure_ascii=False)

    modules = [
        AssessmentModuleDocument(**item)
        for item in first_bundle["collections"]["assessment_modules"]
    ]
    questionnaires = [
        AssessmentQuestionnaireDocument(**item)
        for item in first_bundle["collections"]["assessment_questionnaires"]
    ]

    assert len(modules) == 3
    assert len(questionnaires) == 3
    assert {item.module_code for item in modules} == {"phq9", "gad7", "sleep_observation"}
    assert {item.questionnaire_version for item in questionnaires} == {
        "phq9-cn-v1",
        "gad7-cn-v1",
        "sleep-observation-v1",
    }


def test_complete_assessment_request_rejects_client_supplied_server_fields() -> None:
    schemas = load_module("app.schemas.assessment")

    with pytest.raises(ValidationError):
        schemas.CompleteAssessmentSessionRequest.model_validate(
            {
                "answers": [
                    {
                        "question_key": "q1",
                        "option_key": "0",
                        "score_snapshot": 0,
                    }
                ],
                "object_version": 1,
            }
        )

    with pytest.raises(ValidationError):
        schemas.CompleteAssessmentSessionRequest.model_validate(
            {
                "answers": [{"question_key": "q1", "option_key": "0"}],
                "object_version": 1,
                "result_state": "higher_score",
            }
        )
