"""Business persistence ports; concrete adapters live in infra/database."""

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any, Protocol

from app.infra.database.records import (
    AuditEventRecord,
    AuthSessionRecord,
    IdempotencyOutcome,
    IdempotencyRecord,
)
from app.models.v2.documents import (
    AnonymousIdentityDocument,
    AssessmentModuleDocument,
    AssessmentQuestionnaireDocument,
    AssessmentResultDocument,
    AssessmentSessionDocument,
    ConsentEventDocument,
    DailyMoodRecordDocument,
    IdentityAccessRequestDocument,
    IdentityRecordDocument,
    QuoteEntryDocument,
    SafetySupportTaskDocument,
    SupportResourceDocument,
    TreeholePostDocument,
    TreeholeResponseDocument,
    UserAccountDocument,
    WorkTaskDocument,
)


class DomainRepository(Protocol):
    def transaction(self) -> AbstractAsyncContextManager[None]: ...

    async def get_user(self, user_id: str) -> UserAccountDocument: ...

    async def get_user_by_auth_subject_hash(
        self, subject_hash: str
    ) -> UserAccountDocument | None: ...

    async def create_user(self, user: UserAccountDocument) -> UserAccountDocument: ...

    async def save_user(
        self, user: UserAccountDocument, *, expected_version: int
    ) -> UserAccountDocument: ...

    async def append_consent_event(self, consent: ConsentEventDocument) -> ConsentEventDocument: ...

    async def list_consent_events(self, user_id: str) -> tuple[ConsentEventDocument, ...]: ...

    async def create_identity_record(
        self, identity: IdentityRecordDocument
    ) -> IdentityRecordDocument: ...

    async def save_identity_record(
        self, identity: IdentityRecordDocument, *, expected_version: int
    ) -> IdentityRecordDocument: ...

    async def get_identity_record(self, identity_record_id: str) -> IdentityRecordDocument: ...

    async def get_identity_record_by_user(self, user_id: str) -> IdentityRecordDocument | None: ...

    async def create_anonymous_identity(
        self, anonymous_identity: AnonymousIdentityDocument
    ) -> AnonymousIdentityDocument: ...

    async def get_anonymous_identity(
        self, anonymous_identity_id: str
    ) -> AnonymousIdentityDocument: ...

    async def get_active_anonymous_identity_by_user(
        self, user_id: str
    ) -> AnonymousIdentityDocument | None: ...

    async def list_anonymous_identities(
        self, user_id: str
    ) -> tuple[AnonymousIdentityDocument, ...]: ...

    async def next_consent_id(self) -> str: ...

    async def next_identity_record_id(self) -> str: ...

    async def next_anonymous_identity_id(self) -> str: ...

    async def get_assessment_module(self, module_code: str) -> AssessmentModuleDocument: ...

    async def replace_assessment_module(
        self, module: AssessmentModuleDocument, *, expected_version: int
    ) -> AssessmentModuleDocument: ...

    async def get_assessment_questionnaire(
        self, module_code: str, questionnaire_version: str
    ) -> AssessmentQuestionnaireDocument: ...

    async def create_assessment_session(
        self, session: AssessmentSessionDocument
    ) -> AssessmentSessionDocument: ...

    async def get_assessment_session(self, session_id: str) -> AssessmentSessionDocument: ...

    async def save_assessment_session(
        self, session: AssessmentSessionDocument, *, expected_version: int
    ) -> AssessmentSessionDocument: ...

    async def create_assessment_result(
        self, result: AssessmentResultDocument
    ) -> AssessmentResultDocument: ...

    async def get_assessment_result(self, result_id: str) -> AssessmentResultDocument: ...

    async def get_assessment_result_by_session(
        self, session_id: str
    ) -> AssessmentResultDocument | None: ...

    async def save_assessment_result(
        self, result: AssessmentResultDocument, *, expected_version: int
    ) -> AssessmentResultDocument: ...

    async def list_assessment_results_by_session(
        self, session_id: str
    ) -> tuple[AssessmentResultDocument, ...]: ...

    async def list_assessment_results_by_user(
        self, user_id: str
    ) -> tuple[AssessmentResultDocument, ...]: ...

    async def create_daily_mood_record(
        self, record: DailyMoodRecordDocument
    ) -> DailyMoodRecordDocument: ...

    async def get_daily_mood(self, record_id: str) -> DailyMoodRecordDocument: ...

    async def get_daily_mood_by_user_date(
        self, user_id: str, record_date: str
    ) -> DailyMoodRecordDocument | None: ...

    async def list_daily_mood_records(
        self, user_id: str
    ) -> tuple[DailyMoodRecordDocument, ...]: ...

    async def save_daily_mood_record(
        self, record: DailyMoodRecordDocument, *, expected_version: int
    ) -> DailyMoodRecordDocument: ...

    async def list_available_quote_entries(
        self, record_date: str
    ) -> tuple[QuoteEntryDocument, ...]: ...

    async def list_support_resources(
        self,
        environment_scope: str,
        *,
        resource_set_version: str | None = None,
        now: datetime | None = None,
    ) -> tuple[SupportResourceDocument, ...]: ...

    async def create_safety_support_task(
        self, task: SafetySupportTaskDocument
    ) -> SafetySupportTaskDocument: ...

    async def list_safety_support_tasks(self) -> tuple[SafetySupportTaskDocument, ...]: ...

    async def create_work_task(self, task: WorkTaskDocument) -> WorkTaskDocument: ...

    async def get_work_task(self, task_id: str) -> WorkTaskDocument: ...

    async def list_work_tasks(self) -> tuple[WorkTaskDocument, ...]: ...

    async def save_work_task(
        self, task: WorkTaskDocument, *, expected_version: int
    ) -> WorkTaskDocument: ...

    async def create_treehole_post(self, post: TreeholePostDocument) -> TreeholePostDocument: ...

    async def get_treehole_post(self, post_id: str) -> TreeholePostDocument: ...

    async def save_treehole_post(
        self, post: TreeholePostDocument, *, expected_version: int
    ) -> TreeholePostDocument: ...

    async def list_treehole_posts(self) -> tuple[TreeholePostDocument, ...]: ...

    async def create_treehole_response(
        self, response: TreeholeResponseDocument
    ) -> TreeholeResponseDocument: ...

    async def get_treehole_response(self, response_id: str) -> TreeholeResponseDocument: ...

    async def save_treehole_response(
        self, response: TreeholeResponseDocument, *, expected_version: int
    ) -> TreeholeResponseDocument: ...

    async def list_treehole_responses(
        self, post_id: str
    ) -> tuple[TreeholeResponseDocument, ...]: ...

    async def next_assessment_session_id(self) -> str: ...

    async def next_assessment_result_id(self) -> str: ...

    async def next_daily_mood_id(self) -> str: ...

    async def next_safety_support_task_id(self) -> str: ...

    async def next_work_task_id(self) -> str: ...

    async def next_treehole_post_id(self) -> str: ...

    async def next_treehole_response_id(self) -> str: ...

    async def create_identity_access_request(
        self, request: IdentityAccessRequestDocument
    ) -> IdentityAccessRequestDocument: ...

    async def get_identity_access_request(
        self, request_id: str
    ) -> IdentityAccessRequestDocument: ...

    async def save_identity_access_request(
        self, request: IdentityAccessRequestDocument, *, expected_version: int
    ) -> IdentityAccessRequestDocument: ...

    async def next_identity_access_request_id(self) -> str: ...

    async def list_identity_access_requests(self) -> tuple[IdentityAccessRequestDocument, ...]: ...

    async def extra_collection(self, name: str) -> list[dict[str, Any]]: ...

    async def append_extra_document(self, name: str, document: Mapping[str, Any]) -> None: ...


class SessionRepository(Protocol):
    async def save(self, record: AuthSessionRecord) -> None: ...

    async def replace(self, record: AuthSessionRecord) -> None: ...

    async def get_by_session_id(self, session_id: str) -> AuthSessionRecord | None: ...

    async def get_by_access_token_hash(self, token_hash: str) -> AuthSessionRecord | None: ...

    async def get_by_refresh_token_hash(self, token_hash: str) -> AuthSessionRecord | None: ...

    async def revoke(self, session_id: str, *, now: datetime) -> AuthSessionRecord | None: ...


class IdempotencyRepository(Protocol):
    async def get(
        self, actor_type: str, actor_id: str, route_key: str, idempotency_key: str, *, now: datetime
    ) -> IdempotencyRecord | None: ...

    async def reserve(
        self, record: IdempotencyRecord, *, now: datetime
    ) -> IdempotencyRecord | None: ...

    async def complete(
        self,
        record_id: str,
        *,
        outcome: IdempotencyOutcome,
        response_status: int,
        response_digest: str,
        now: datetime,
    ) -> IdempotencyRecord: ...


class AuditRepository(Protocol):
    async def append(self, event: AuditEventRecord) -> AuditEventRecord: ...

    async def list(self) -> tuple[AuditEventRecord, ...]: ...
