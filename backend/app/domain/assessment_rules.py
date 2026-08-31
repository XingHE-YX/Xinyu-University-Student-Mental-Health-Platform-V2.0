"""Frozen assessment questionnaires and server-side scoring rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from app.domain.models import (
    AssessmentModuleDocument,
    AssessmentQuestionnaireDocument,
    QuestionnaireQuestionModel,
    QuestionOptionModel,
)
from app.schemas.errors import ApiException

ModuleCode = Literal["phq9", "gad7", "sleep_observation"]

SEED_TIMESTAMP = datetime(2026, 8, 31, tzinfo=UTC)
NON_DIAGNOSTIC_COPY_VERSION = "assessment-copy-v1"
SCORING_RULE_VERSION = "assessment-rules-v1"
PHQ9_VERSION = "phq9-cn-v1"
GAD7_VERSION = "gad7-cn-v1"
SLEEP_VERSION = "sleep-observation-v1"
SLEEP_Q8_REFUSAL_OPTION_KEY = "prefer_not_to_answer"
PHQ9_Q9_KEY = "q9"

PHQ_GAD_BOUNDARY_NOTICE = "这是一项筛查结果，不是诊断。"
SLEEP_BOUNDARY_NOTICE = "这次结果用于睡眠与作息的自我观察，不作为诊断依据。"


class AssessmentValidationError(ApiException):
    def __init__(self, code: str = "VALIDATION_FAILED") -> None:
        super().__init__(422, code)


@dataclass(frozen=True, slots=True)
class ScoreOutcome:
    module_code: ModuleCode
    scoring_rule_version: str
    visible_copy_version: str
    fixed_summary: str
    boundary_notice: str
    result_state: Literal["ordinary", "higher_score"]
    score: int | None
    reference_band: str | None
    safety_triggered: bool
    dimension_summary: dict[str, object]
    answers_snapshot: list[dict[str, object]]


@dataclass(frozen=True, slots=True)
class CatalogQuestion:
    question_key: str
    order: int
    text: str
    options: tuple[QuestionOptionModel, ...]
    required: bool = True
    multiple: bool = False


@dataclass(frozen=True, slots=True)
class CatalogQuestionnaire:
    module: AssessmentModuleDocument
    questionnaire: AssessmentQuestionnaireDocument
    questions: tuple[CatalogQuestion, ...]


def build_seed_documents() -> dict[
    str, list[AssessmentModuleDocument | AssessmentQuestionnaireDocument]
]:
    phq9 = _phq9_catalog()
    gad7 = _gad7_catalog()
    sleep = _sleep_catalog()
    return {
        "assessment_modules": [phq9.module, gad7.module, sleep.module],
        "assessment_questionnaires": [
            phq9.questionnaire,
            gad7.questionnaire,
            sleep.questionnaire,
        ],
    }


def questionnaire_catalog(module_code: ModuleCode) -> CatalogQuestionnaire:
    if module_code == "phq9":
        return _phq9_catalog()
    if module_code == "gad7":
        return _gad7_catalog()
    if module_code == "sleep_observation":
        return _sleep_catalog()
    raise AssessmentValidationError()


def score_questionnaire(module_code: ModuleCode, answers: list[tuple[str, str]]) -> ScoreOutcome:
    catalog = questionnaire_catalog(module_code)
    validated = _validate_answers(catalog, answers)
    if module_code == "phq9":
        return _score_phq9(validated)
    if module_code == "gad7":
        return _score_gad7(validated)
    return _score_sleep(validated)


def _phq9_catalog() -> CatalogQuestionnaire:
    option_labels = ("从来没有", "有几天", "超过一半天数", "接近每天")
    scored_options = tuple(
        QuestionOptionModel(option_key=str(score), label=label, score=score)
        for score, label in enumerate(option_labels)
    )
    impact_options = (
        QuestionOptionModel(option_key="none", label="完全没有困难", score=0),
        QuestionOptionModel(option_key="some", label="有一些困难", score=0),
        QuestionOptionModel(option_key="very", label="非常困难", score=0),
        QuestionOptionModel(option_key="extreme", label="极度困难", score=0),
    )
    questions = (
        CatalogQuestion("q1", 1, "做任何事都觉得沉闷或者根本不想做任何事。", scored_options),
        CatalogQuestion("q2", 2, "情绪低落、抑郁或绝望。", scored_options),
        CatalogQuestion("q3", 3, "难于入睡；半夜会醒，或相反，睡觉时间过多。", scored_options),
        CatalogQuestion("q4", 4, "觉得疲倦或没有活力。", scored_options),
        CatalogQuestion("q5", 5, "胃口极差或饮食过量。", scored_options),
        CatalogQuestion(
            "q6",
            6,
            "不喜欢自己，觉得自己做得不好、对自己失望或有负家人期望。",
            scored_options,
        ),
        CatalogQuestion("q7", 7, "难于集中精神做事，例如看报纸或看电视。", scored_options),
        CatalogQuestion(
            "q8",
            8,
            "其他人反映你行动或说话迟缓；或者相反，你比平常活动更多，坐立不安、停不下来。",
            scored_options,
        ),
        CatalogQuestion("q9", 9, "想到自己最好去死或者自残。", scored_options),
        CatalogQuestion(
            "impact",
            10,
            "这些问题对你的学习、日常事务或与人相处造成多大困难？",
            impact_options,
        ),
    )
    return CatalogQuestionnaire(
        module=AssessmentModuleDocument(
            _id="assessment-module-phq9",
            module_code="phq9",
            title="近两周情绪状态",
            description="用于自我观察近两周的情绪状态，不替代专业评估。",
            expected_minutes=2,
            current_questionnaire_version=PHQ9_VERSION,
            enabled=True,
            created_at=SEED_TIMESTAMP,
            updated_at=SEED_TIMESTAMP,
            version=1,
        ),
        questionnaire=_build_questionnaire_document(
            document_id="assessment-questionnaire-phq9-v1",
            module_code="phq9",
            questionnaire_version=PHQ9_VERSION,
            questions=questions,
            score_rule={
                "scoring_rule_version": SCORING_RULE_VERSION,
                "reference_bands": [
                    {"min": 0, "max": 4, "label": "0-4"},
                    {"min": 5, "max": 9, "label": "5-9"},
                    {"min": 10, "max": 14, "label": "10-14"},
                    {"min": 15, "max": 19, "label": "15-19"},
                    {"min": 20, "max": 27, "label": "20-27"},
                ],
                "impact_question_key": "impact",
                "safety_question_key": PHQ9_Q9_KEY,
            },
        ),
        questions=questions,
    )


def _gad7_catalog() -> CatalogQuestionnaire:
    option_labels = ("从来没有", "有几天", "超过一半天数", "接近每天")
    scored_options = tuple(
        QuestionOptionModel(option_key=str(score), label=label, score=score)
        for score, label in enumerate(option_labels)
    )
    questions = (
        CatalogQuestion("q1", 1, "感觉心神不安、焦虑或高度紧张。", scored_options),
        CatalogQuestion("q2", 2, "不能停止或控制担心。", scored_options),
        CatalogQuestion("q3", 3, "为各种各样的事情过度担心。", scored_options),
        CatalogQuestion("q4", 4, "难以放松。", scored_options),
        CatalogQuestion("q5", 5, "非常不安静以至于难以坐定。", scored_options),
        CatalogQuestion("q6", 6, "变得易恼火或易急躁。", scored_options),
        CatalogQuestion("q7", 7, "害怕发生可怕的事情。", scored_options),
    )
    return CatalogQuestionnaire(
        module=AssessmentModuleDocument(
            _id="assessment-module-gad7",
            module_code="gad7",
            title="近两周焦虑状态",
            description="用于自我观察近两周的紧绷和担心，不替代专业评估。",
            expected_minutes=2,
            current_questionnaire_version=GAD7_VERSION,
            enabled=True,
            created_at=SEED_TIMESTAMP,
            updated_at=SEED_TIMESTAMP,
            version=1,
        ),
        questionnaire=_build_questionnaire_document(
            document_id="assessment-questionnaire-gad7-v1",
            module_code="gad7",
            questionnaire_version=GAD7_VERSION,
            questions=questions,
            score_rule={
                "scoring_rule_version": SCORING_RULE_VERSION,
                "reference_bands": [
                    {"min": 0, "max": 4, "label": "0-4"},
                    {"min": 5, "max": 9, "label": "5-9"},
                    {"min": 10, "max": 14, "label": "10-14"},
                    {"min": 15, "max": 21, "label": "15-21"},
                ],
            },
        ),
        questions=questions,
    )


def _sleep_catalog() -> CatalogQuestionnaire:
    questions = (
        CatalogQuestion(
            "q1",
            1,
            "最近 7 天，你躺下准备睡觉的时间大致稳定吗？",
            (
                _option("stable", "基本稳定", 0),
                _option("occasional_variation", "偶尔变化", 1),
                _option("frequent_variation", "经常变化", 2),
                _option("large_variation", "每天差别较大", 3),
            ),
        ),
        CatalogQuestion(
            "q2",
            2,
            "最近 7 天，你大多数晚上实际睡了多久？",
            (
                _option("under_5", "少于 5 小时", 0),
                _option("5_to_6", "5–不足 6 小时", 1),
                _option("6_to_7", "6–不足 7 小时", 2),
                _option("7_to_9", "7–9 小时", 3),
                _option("over_9", "超过 9 小时", 4),
            ),
        ),
        CatalogQuestion(
            "q3",
            3,
            "躺下并决定睡觉后，你通常多久能睡着？",
            (
                _option("within_15", "15 分钟内", 0),
                _option("16_to_30", "16–30 分钟", 1),
                _option("31_to_60", "31–60 分钟", 2),
                _option("over_60", "超过 60 分钟", 3),
            ),
        ),
        CatalogQuestion(
            "q4",
            4,
            "夜里醒来后，你重新睡着的情况更接近哪一种？",
            (
                _option("easy_to_resume", "很少醒或容易再睡", 0),
                _option("needs_a_while", "偶尔需要一会儿", 1),
                _option("takes_long", "经常需要较久", 2),
                _option("hard_to_sleep_again", "经常难以再睡", 3),
            ),
        ),
        CatalogQuestion(
            "q5",
            5,
            "早上醒来时，你通常是什么感觉？",
            (
                _option("good", "精神较好", 0),
                _option("okay", "还可以", 1),
                _option("tired", "有些疲惫", 2),
                _option("very_tired", "很疲惫", 3),
            ),
        ),
        CatalogQuestion(
            "q6",
            6,
            "最近 7 天，睡眠状态对上课、学习、注意力或情绪的影响如何？",
            (
                _option("none", "几乎没有", 0),
                _option("a_little", "有一点", 1),
                _option("obvious", "比较明显", 2),
                _option("major_impact", "影响很大", 3),
            ),
        ),
        CatalogQuestion(
            "q7",
            7,
            "即使已经没有紧急的事需要做，我还是会继续刷信息、追内容或做别的事，拖到更晚才睡。",
            (
                _option("never", "从不", 0),
                _option("occasionally", "偶尔", 1),
                _option("often", "经常", 2),
                _option("almost_daily", "几乎每天", 3),
            ),
        ),
        CatalogQuestion(
            "q8",
            8,
            "当你睡前仍不想睡时，更接近下面哪些情况？",
            (
                _option("not_sleepy", "还不困，作息已经乱了", 0),
                _option("extend_personal_time", "想把属于自己的时间再延长一点", 0),
                _option("phone_content", "刷手机、追剧、游戏等停不下来", 0),
                _option("unfinished_work", "学习、工作或其他事情还没完成", 0),
                _option("overthinking", "脑子停不下来，反复想事情", 0),
                _option("avoid_tomorrow", "不太想面对明天", 0),
                _option("environment_impact", "环境、噪音或室友作息影响", 0),
                _option("physical_discomfort", "身体不舒服", 0),
                _option("unclear", "说不清", 0),
                _option(SLEEP_Q8_REFUSAL_OPTION_KEY, "不想回答", 0),
            ),
            required=False,
            multiple=True,
        ),
    )
    return CatalogQuestionnaire(
        module=AssessmentModuleDocument(
            _id="assessment-module-sleep-observation",
            module_code="sleep_observation",
            title="睡眠与作息自我观察",
            description="用于记录最近 7 天的睡眠与作息感受，不作为医学量表。",
            expected_minutes=3,
            current_questionnaire_version=SLEEP_VERSION,
            enabled=True,
            created_at=SEED_TIMESTAMP,
            updated_at=SEED_TIMESTAMP,
            version=1,
        ),
        questionnaire=_build_questionnaire_document(
            document_id="assessment-questionnaire-sleep-v1",
            module_code="sleep_observation",
            questionnaire_version=SLEEP_VERSION,
            questions=questions,
            score_rule={
                "scoring_rule_version": SCORING_RULE_VERSION,
                "dimensions": [
                    "rhythm",
                    "duration_fact",
                    "bedtime_resistance",
                    "bedtime_reasons",
                    "recovery_daytime_impact",
                ],
            },
        ),
        questions=questions,
    )


def _build_questionnaire_document(
    *,
    document_id: str,
    module_code: ModuleCode,
    questionnaire_version: str,
    questions: tuple[CatalogQuestion, ...],
    score_rule: dict[str, object],
) -> AssessmentQuestionnaireDocument:
    return AssessmentQuestionnaireDocument(
        _id=document_id,
        module_code=module_code,
        questionnaire_version=questionnaire_version,
        questions=[
            QuestionnaireQuestionModel(
                question_key=question.question_key,
                order=question.order,
                text=question.text,
                options=list(question.options),
            )
            for question in questions
        ],
        score_rule=score_rule,
        non_diagnostic_copy_version=NON_DIAGNOSTIC_COPY_VERSION,
        enabled=True,
        published_at=SEED_TIMESTAMP,
        created_at=SEED_TIMESTAMP,
        updated_at=SEED_TIMESTAMP,
        version=1,
    )


def _validate_answers(
    catalog: CatalogQuestionnaire,
    answers: list[tuple[str, str]],
) -> list[tuple[CatalogQuestion, list[QuestionOptionModel]]]:
    grouped: dict[str, list[QuestionOptionModel]] = {}
    order_seen: list[str] = []
    current_index = 0
    for question_key, option_key in answers:
        if current_index >= len(catalog.questions):
            raise AssessmentValidationError()
        while (
            current_index < len(catalog.questions)
            and catalog.questions[current_index].question_key != question_key
        ):
            if catalog.questions[current_index].required:
                raise AssessmentValidationError()
            current_index += 1
        if current_index >= len(catalog.questions):
            raise AssessmentValidationError()
        question = catalog.questions[current_index]
        if not question.multiple and question_key in grouped:
            raise AssessmentValidationError()
        option = next((item for item in question.options if item.option_key == option_key), None)
        if option is None:
            raise AssessmentValidationError()
        if question.multiple:
            if option in grouped.get(question_key, []):
                raise AssessmentValidationError()
        grouped.setdefault(question_key, []).append(option)
        if not order_seen or order_seen[-1] != question_key:
            order_seen.append(question_key)
        if not question.multiple:
            current_index += 1

    for question in catalog.questions:
        if question.required and question.question_key not in grouped:
            raise AssessmentValidationError()
    extra_keys = {
        key
        for key in grouped
        if key not in {question.question_key for question in catalog.questions}
    }
    if extra_keys:
        raise AssessmentValidationError()

    q8_answers = grouped.get("q8", [])
    if q8_answers and any(item.option_key == SLEEP_Q8_REFUSAL_OPTION_KEY for item in q8_answers):
        if len(q8_answers) != 1:
            raise AssessmentValidationError()

    return [(question, grouped.get(question.question_key, [])) for question in catalog.questions]


def _score_phq9(
    validated: list[tuple[CatalogQuestion, list[QuestionOptionModel]]],
) -> ScoreOutcome:
    answers_snapshot: list[dict[str, object]] = []
    score = 0
    safety_triggered = False
    for question, options in validated:
        option = options[0]
        answers_snapshot.append(
            {
                "question_key": question.question_key,
                "option_key": option.option_key,
                "score_snapshot": option.score,
            }
        )
        if question.question_key == "impact":
            continue
        score += option.score
        if question.question_key == PHQ9_Q9_KEY and option.score > 0:
            safety_triggered = True
    reference_band, fixed_summary = _phq9_band(score)
    return ScoreOutcome(
        module_code="phq9",
        scoring_rule_version=SCORING_RULE_VERSION,
        visible_copy_version=NON_DIAGNOSTIC_COPY_VERSION,
        fixed_summary=fixed_summary,
        boundary_notice=PHQ_GAD_BOUNDARY_NOTICE,
        result_state="higher_score" if score >= 10 else "ordinary",
        score=score,
        reference_band=reference_band,
        safety_triggered=safety_triggered,
        dimension_summary={},
        answers_snapshot=answers_snapshot,
    )


def _score_gad7(
    validated: list[tuple[CatalogQuestion, list[QuestionOptionModel]]],
) -> ScoreOutcome:
    score = 0
    answers_snapshot: list[dict[str, object]] = []
    for question, options in validated:
        option = options[0]
        score += option.score
        answers_snapshot.append(
            {
                "question_key": question.question_key,
                "option_key": option.option_key,
                "score_snapshot": option.score,
            }
        )
    reference_band, fixed_summary = _gad7_band(score)
    return ScoreOutcome(
        module_code="gad7",
        scoring_rule_version=SCORING_RULE_VERSION,
        visible_copy_version=NON_DIAGNOSTIC_COPY_VERSION,
        fixed_summary=fixed_summary,
        boundary_notice=PHQ_GAD_BOUNDARY_NOTICE,
        result_state="higher_score" if score >= 10 else "ordinary",
        score=score,
        reference_band=reference_band,
        safety_triggered=False,
        dimension_summary={},
        answers_snapshot=answers_snapshot,
    )


def _score_sleep(
    validated: list[tuple[CatalogQuestion, list[QuestionOptionModel]]],
) -> ScoreOutcome:
    answer_map = {question.question_key: options for question, options in validated}
    q1 = answer_map["q1"][0]
    q2 = answer_map["q2"][0]
    q3 = answer_map["q3"][0]
    q4 = answer_map["q4"][0]
    q5 = answer_map["q5"][0]
    q6 = answer_map["q6"][0]
    q7 = answer_map["q7"][0]
    q8 = answer_map.get("q8", [])

    resistance_index = max(q3.score, q4.score, q7.score)
    recovery_index = max(q5.score, q6.score)
    bedtime_reasons = [item.label for item in q8]
    if not q8:
        bedtime_reasons_summary: list[str] = []
    elif q8[0].option_key == SLEEP_Q8_REFUSAL_OPTION_KEY:
        bedtime_reasons_summary = ["你选择暂不说明睡前原因"]
    else:
        bedtime_reasons_summary = bedtime_reasons

    dimension_summary: dict[str, object] = {
        "rhythm": ("比较稳定", "有一些波动", "波动较多", "波动很明显")[q1.score],
        "duration_fact": f"你记录的大多数夜晚实际睡眠约为 {q2.label}",
        "bedtime_resistance": ("暂不明显", "偶尔出现", "比较明显", "经常出现")[resistance_index],
        "bedtime_reasons": bedtime_reasons_summary
        if bedtime_reasons_summary
        else ["这次没有记录睡前原因"],
        "recovery_daytime_impact": (
            "恢复感较好",
            "偶尔不够理想",
            "经常不够理想",
            "影响较明显",
        )[recovery_index],
    }
    answers_snapshot = [
        {
            "question_key": question.question_key,
            "option_key": option.option_key,
            "score_snapshot": option.score,
        }
        for question, options in validated
        for option in options
    ]
    return ScoreOutcome(
        module_code="sleep_observation",
        scoring_rule_version=SCORING_RULE_VERSION,
        visible_copy_version=NON_DIAGNOSTIC_COPY_VERSION,
        fixed_summary="这次记录整理了你的作息节律、睡前阻力和恢复感受，供你自我观察。",
        boundary_notice=SLEEP_BOUNDARY_NOTICE,
        result_state="ordinary",
        score=None,
        reference_band=None,
        safety_triggered=False,
        dimension_summary=dimension_summary,
        answers_snapshot=answers_snapshot,
    )


def _phq9_band(score: int) -> tuple[str, str]:
    if score <= 4:
        return "0-4", "近期情绪相关信号较少"
    if score <= 9:
        return "5-9", "近期有一些情绪困扰"
    if score <= 14:
        return "10-14", "近期困扰较明显，建议优先查看支持资源"
    if score <= 19:
        return "15-19", "近期困扰较重，建议尽快寻求专业支持"
    return "20-27", "近期困扰很重，建议尽快获得专业支持"


def _gad7_band(score: int) -> tuple[str, str]:
    if score <= 4:
        return "0-4", "近期紧绷和担心的信号较少"
    if score <= 9:
        return "5-9", "近期有一些紧绷或担心"
    if score <= 14:
        return "10-14", "近期焦虑相关困扰较明显，建议查看支持资源"
    return "15-21", "近期困扰较重，建议尽快与专业人员交流"


def _option(option_key: str, label: str, score: int) -> QuestionOptionModel:
    return QuestionOptionModel(option_key=option_key, label=label, score=score)
