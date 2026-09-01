"""Student today aggregation projection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from app.config.settings import Settings
from app.domain.models import AssessmentResultDocument
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.protocols import RepositoryNotFound
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager
from app.services.mood_service import MoodFact
from app.services.quote_service import QuoteProjection, QuoteService
from app.services.support_resource_service import SupportResourceService

SHANGHAI = ZoneInfo("Asia/Shanghai")

ASSESSMENT_SHORTCUTS = {
    "phq9": ("PHQ-9", "情绪观察"),
    "gad7": ("GAD-7", "焦虑观察"),
    "sleep_observation": ("睡眠观察", "作息与睡眠观察"),
}


class AssessmentShortcut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_code: Literal["phq9", "gad7", "sleep_observation"]
    title: str
    description: str
    latest_completed_date: str | None
    latest_completed_text: str
    safety_entry_required: bool = False


class SupportEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    resource_version: str | None
    resource_count: int


class TodayProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: QuoteProjection | None
    mood_today: MoodFact | None
    assessment_shortcuts: list[AssessmentShortcut]
    support_entry: SupportEntry


class TodayService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: InMemoryDomainDataRepository,
        session_repository: InMemorySessionRepository,
        token_manager: TokenManager,
        quote_service: QuoteService,
        support_resource_service: SupportResourceService,
        now_provider: object | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.sessions = session_repository
        self.tokens = token_manager
        self.quote_service = quote_service
        self.support_resources = support_resource_service
        self._now_provider = now_provider

    def get_today(self, access_token: str) -> TodayProjection:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        self._ensure_private_access(subject.subject_id)
        today = self._today()
        mood = self.repository.get_daily_mood_by_user_date(subject.subject_id, today)
        quote = self.quote_service.get_daily_quote(now=self._now())
        resources = self.support_resources.list_resources(context="normal")
        return TodayProjection(
            quote=quote.quote,
            mood_today=MoodFact(
                record_id=mood.document_id,
                record_date=mood.record_date,
                mood_code=mood.mood_code,
                saved_at=mood.created_at,
                version=mood.version,
            )
            if mood is not None and mood.deleted_at is None
            else None,
            assessment_shortcuts=self._assessment_shortcuts(subject.subject_id),
            support_entry=SupportEntry(
                status=resources.status,
                resource_version=resources.resource_version,
                resource_count=len(resources.resources),
            ),
        )

    def _assessment_shortcuts(self, user_id: str) -> list[AssessmentShortcut]:
        ordinary_results: dict[
            Literal["phq9", "gad7", "sleep_observation"],
            AssessmentResultDocument,
        ] = {}
        safety_entry_required = False
        for result in self.repository.list_assessment_results_by_user(user_id):
            if result.result_state == "safety_support":
                safety_entry_required = True
                continue
            if result.module_code not in ordinary_results:
                ordinary_results[result.module_code] = result
        shortcuts: list[AssessmentShortcut] = []
        for module_code, (title, description) in ASSESSMENT_SHORTCUTS.items():
            selected_result = ordinary_results.get(
                cast(Literal["phq9", "gad7", "sleep_observation"], module_code)
            )
            completed_date = (
                _shanghai_date(selected_result.created_at)
                if selected_result is not None
                else None
            )
            shortcuts.append(
                AssessmentShortcut(
                    module_code=module_code,  # type: ignore[arg-type]
                    title=title,
                    description=description,
                    latest_completed_date=completed_date,
                    latest_completed_text=completed_date or "尚未记录",
                    safety_entry_required=safety_entry_required and module_code == "phq9",
                )
            )
        return shortcuts

    def _ensure_private_access(self, user_id: str) -> None:
        user = self.repository.get_user(user_id)
        if user.status != "active":
            raise ApiException(403, "FORBIDDEN")
        if user.base_consent_status != "accepted":
            raise ApiException(403, "CONSENT_REQUIRED")
        if not user.identity_record_id:
            raise ApiException(403, "IDENTITY_REQUIRED")
        try:
            identity = self.repository.get_identity_record(user.identity_record_id)
        except RepositoryNotFound as error:
            raise ApiException(403, "IDENTITY_REQUIRED") from error
        if identity.user_id != user.document_id or identity.verification_status != "verified":
            raise ApiException(403, "IDENTITY_REQUIRED")

    def _now(self) -> datetime:
        if callable(self._now_provider):
            value = self._now_provider()
            if isinstance(value, datetime):
                return value
        return datetime.now(UTC)

    def _today(self) -> str:
        return _shanghai_date(self._now())


def _shanghai_date(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(SHANGHAI).date().isoformat()
