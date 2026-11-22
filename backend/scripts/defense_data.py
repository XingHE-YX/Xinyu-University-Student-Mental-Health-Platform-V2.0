"""Build the isolated 2026 defense cohort using the application's stored schemas."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from hashlib import sha256
from random import Random
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.models.v2.documents import (
    AnonymousIdentityDocument,
    AssessmentAnswerModel,
    AssessmentQuestionnaireDocument,
    AssessmentResultDocument,
    AssessmentSessionDocument,
    ConsentEventDocument,
    IdentityRecordDocument,
    TreeholePostDocument,
    UserAccountDocument,
)
from app.services.v2.identity_service import IdentityCipher
from app.services.v2.rules.assessment import (
    PHQ9_Q9_KEY,
    ModuleCode,
    questionnaire_catalog,
    questionnaire_questions,
    score_questionnaire,
)
from scripts.defense_cases import CASE_ROWS

PREFIX = "defense2026-"
ENVIRONMENT_ID = "xinyu-v2-demo-d3g8qbyfu11a452ff"
RESERVED_NUMBER = "10425326"
BASE_CONSENT = "base-consent-v1"
COMMUNITY_CONSENT = "community-consent-v1"
SHANGHAI = ZoneInfo("Asia/Shanghai")
START = datetime(2026, 8, 27, tzinfo=SHANGHAI)
END = datetime(2026, 11, 22, 23, 59, 59, tzinfo=SHANGHAI)
MODULES: tuple[ModuleCode, ...] = ("phq9", "gad7", "sleep_observation")
Band = Literal["low", "elevated", "high"]
Document = dict[str, Any]
Bundle = dict[str, list[Document]]
COLLECTIONS = (
    "user_accounts",
    "identity_records",
    "anonymous_identities",
    "consent_records",
    "assessment_sessions",
    "assessment_results",
    "treehole_posts",
)


def roster() -> dict[str, tuple[str, str]]:
    return {
        f"{PREFIX}user-{index + 1:02d}": (name, f"104253{index + 40:02d}")
        for index, (name, _, _) in enumerate(CASE_ROWS)
    }


def band(module: str, score: int | None) -> Band | None:
    if score is None or module not in {"phq9", "gad7"}:
        return None
    if score >= (20 if module == "phq9" else 15):
        return "high"
    return "elevated" if score >= 5 else "low"


def _metadata(document_id: str, created: datetime, updated: datetime | None = None) -> Document:
    return {
        "_id": document_id,
        "created_at": created,
        "updated_at": updated or created,
        "version": 1,
    }


def _digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def _timestamp(day: int, hour: int, rng: Random) -> datetime:
    return START + timedelta(days=day, hours=hour, minutes=rng.randrange(5, 59))


def _target(index: int, module: ModuleCode, stage: int, deep_night: bool, rng: Random) -> int:
    high_threshold = 20 if module == "phq9" else 15
    if stage == 5:
        if index < 15:
            return rng.randrange(1, 5)
        if index < 27 or (index + (module == "gad7")) % 3 == 0:
            return rng.randrange(5, min(high_threshold, 13))
        return rng.randrange(high_threshold, high_threshold + 4)
    if deep_night:
        if index >= 27 and stage in {2, 4}:
            return rng.randrange(high_threshold, high_threshold + 3)
        if index < 15 and (index + stage * 2 + (module == "gad7")) % 5 < 3:
            return rng.randrange(1, 5)
        return rng.randrange(5, min(high_threshold, (10, 11, 13, 12, 15)[stage]))
    if index < 15:
        return rng.randrange(0, 8 if stage in {2, 4} else 5)
    if index < 27:
        return rng.randrange(2 + stage // 2, min(high_threshold, 9 + stage * 2))
    return rng.randrange(7 + stage, high_threshold + 2)


def _answers(
    questionnaire: AssessmentQuestionnaireDocument, target: int, rng: Random
) -> list[tuple[str, str]]:
    questions = questionnaire_questions(questionnaire)
    if questionnaire.module_code == "sleep_observation":
        return [
            (question.question_key, rng.choice(question.options).option_key)
            for question in questions
        ]

    score_keys = [
        item.question_key for item in questions if item.question_key not in {PHQ9_Q9_KEY, "impact"}
    ]
    scores = dict.fromkeys(score_keys, 0)
    for _ in range(target):
        chosen = rng.choice([key for key in score_keys if scores[key] < 3])
        scores[chosen] += 1
    return [
        (
            question.question_key,
            question.options[min(target // 6, 3)].option_key
            if question.question_key == "impact"
            else next(
                item.option_key
                for item in question.options
                if item.score == scores.get(question.question_key, 0)
            ),
        )
        for question in questions
    ]


def build_bundle(
    cipher: IdentityCipher,
    questionnaires: Mapping[ModuleCode, AssessmentQuestionnaireDocument],
) -> Bundle:
    collections: Bundle = {name: [] for name in COLLECTIONS}
    stages = ((0, 7), (9, 20), (23, 36), (39, 53), (56, 68), (71, 87))
    for index, (user_id, (name, student_number)) in enumerate(roster().items()):
        rng = Random(20260901 + index * 701)
        alias, posts = CASE_ROWS[index][1:]
        case_id = f"{PREFIX}{index + 1:02d}"
        registered = START - timedelta(hours=index + 2)
        identity_id, anonymous_id = f"{case_id}-identity", f"{case_id}-anon"
        identity = IdentityRecordDocument(
            **_metadata(identity_id, registered),
            user_id=user_id,
            verification_status="verified",
            student_name_ciphertext=cipher.encrypt(name),
            student_number_ciphertext=cipher.encrypt(student_number),
            provider_reference_hash=_digest(f"{case_id}-synthetic"),
            verified_at=registered,
            access_version=1,
        )
        account = UserAccountDocument(
            **_metadata(user_id, registered),
            auth_subject_hash=_digest(f"{user_id}-offline-synthetic-subject"),
            status="active",
            base_consent_status="accepted",
            base_consent_version=BASE_CONSENT,
            base_consent_at=registered,
            community_consent_status="accepted",
            community_consent_version=COMMUNITY_CONSENT,
            community_consent_at=registered,
            identity_record_id=identity_id,
            anonymous_identity_id=anonymous_id,
        )
        display_name = f"{alias} · 演示"
        anonymous = AnonymousIdentityDocument(
            **_metadata(anonymous_id, registered),
            user_id=user_id,
            display_name=display_name,
            generation_version="anon-v1",
            status="active",
        )
        collections["user_accounts"].append(account.model_dump(by_alias=True))
        collections["identity_records"].append(identity.model_dump(by_alias=True))
        collections["anonymous_identities"].append(anonymous.model_dump(by_alias=True))
        for kind, version in (
            ("base_service", BASE_CONSENT),
            ("community_content", COMMUNITY_CONSENT),
        ):
            consent = ConsentEventDocument.model_validate(
                {
                    **_metadata(f"{case_id}-{kind}", registered),
                    "user_id": user_id,
                    "consent_kind": kind,
                    "action": "accepted",
                    "document_version": version,
                    "source": "admin_seed",
                    "occurred_at": registered,
                    "request_id": f"{case_id}-{kind}-seed",
                }
            )
            collections["consent_records"].append(consent.model_dump(by_alias=True))

        for module_index, module in enumerate(MODULES):
            questionnaire = questionnaires[module]
            skipped = (index + module_index) % 4 + 1 if (index + module_index) % 2 else -1
            for stage, (first, last) in enumerate(stages):
                if stage == skipped:
                    continue
                day = (
                    (0 if index == 0 else 87)
                    if (index, module_index, stage) in {(0, 0, 0), (29, 2, 5)}
                    else rng.randint(first, last)
                )
                if index == 29 and module_index == 2 and stage == 5:
                    hour = 23
                elif stage < 5 and (index * 3 + stage + module_index) % 5 < 2:
                    hour = rng.choice((0, 1, 2, 3, 23))
                else:
                    hour = rng.choice((8, 10, 12, 14, 18, 19, 21, 22))
                done = _timestamp(day, hour, rng)
                started = done - timedelta(minutes=rng.randint(2, 8))
                score = (
                    0
                    if module == "sleep_observation"
                    else _target(index, module, stage, hour == 23 or hour < 4, rng)
                )
                outcome = score_questionnaire(questionnaire, _answers(questionnaire, score, rng))
                answers = [
                    AssessmentAnswerModel.model_validate(item) for item in outcome.answers_snapshot
                ]
                session_id = f"{case_id}-{module}-s{stage + 1}"
                result_id = f"{case_id}-{module}-r{stage + 1}"
                session = AssessmentSessionDocument(
                    **_metadata(session_id, started, done),
                    user_id=user_id,
                    module_code=module,
                    questionnaire_version=questionnaire.questionnaire_version,
                    state="completed",
                    answers=answers,
                    answered_count=len(answers),
                    safety_triggered=False,
                    client_idempotency_key=session_id,
                    started_at=started,
                    completed_at=done,
                    expires_at=started + timedelta(hours=24),
                )
                result = AssessmentResultDocument(
                    **_metadata(result_id, done),
                    session_id=session_id,
                    user_id=user_id,
                    module_code=module,
                    answers_snapshot=answers,
                    scoring_rule_version=outcome.scoring_rule_version,
                    fixed_summary=outcome.fixed_summary,
                    reference_band=outcome.reference_band,
                    boundary_notice=outcome.boundary_notice,
                    result_state=outcome.result_state,
                    score=outcome.score,
                    dimension_summary=outcome.dimension_summary,
                    safety_state="not_triggered",
                    visible_copy_version=outcome.visible_copy_version,
                )
                collections["assessment_sessions"].append(session.model_dump(by_alias=True))
                collections["assessment_results"].append(result.model_dump(by_alias=True))

        post_ranges = (
            ((0, 18), (23, 42), (45, 66), (69, 87))
            if len(posts) == 4
            else ((0, 22), (24, 58), (60, 87))
        )
        for post_index, (body, (first, last)) in enumerate(zip(posts, post_ranges, strict=True)):
            hour = (
                rng.choice((0, 1, 2, 23))
                if index >= 15 and post_index == 1
                else rng.choice((8, 11, 13, 16, 19, 21, 22))
            )
            day = (
                0
                if (index, post_index) == (0, 0)
                else 87
                if (index, post_index) == (29, 2)
                else rng.randint(first, last)
            )
            created = _timestamp(day, hour, rng)
            post = TreeholePostDocument(
                **_metadata(f"{case_id}-post-{post_index + 1}", created),
                author_user_id=user_id,
                anonymous_identity_id=anonymous_id,
                display_name_snapshot=display_name,
                body_sanitized=body,
                body_hash=_digest(body),
                visibility_state="published",
                review_state="automated_checked",
                safety_state="not_triggered",
                community_consent_version=COMMUNITY_CONSENT,
            )
            collections["treehole_posts"].append(post.model_dump(by_alias=True))
    return collections


def local_questionnaires() -> dict[ModuleCode, AssessmentQuestionnaireDocument]:
    return {module: questionnaire_catalog(module).questionnaire for module in MODULES}


def dashboard_snapshot(bundle: Bundle) -> Document:
    case_ids = {user: f"D{index + 1:02d}" for index, user in enumerate(roster())}
    return {
        "batch": PREFIX.rstrip("-"),
        "timezone": SHANGHAI.key,
        "start": START.date().isoformat(),
        "end": END.date().isoformat(),
        "assessments": sorted(
            (
                {
                    "caseId": case_ids[result["user_id"]],
                    "at": result["created_at"].astimezone(SHANGHAI).isoformat(),
                    "module": result["module_code"],
                    "band": band(result["module_code"], result["score"]),
                }
                for result in bundle["assessment_results"]
            ),
            key=lambda item: item["at"],
        ),
        "posts": sorted(
            (
                {
                    "caseId": case_ids[post["author_user_id"]],
                    "at": post["created_at"].astimezone(SHANGHAI).isoformat(),
                }
                for post in bundle["treehole_posts"]
            ),
            key=lambda item: item["at"],
        ),
    }
