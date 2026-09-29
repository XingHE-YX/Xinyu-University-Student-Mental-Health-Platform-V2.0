"""CloudBase implementation of the existing typed domain repository contract."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import ValidationError

from app.domain.models import (
    AnonymousIdentityDocument,
    AssessmentModuleDocument,
    AssessmentQuestionnaireDocument,
    AssessmentResultDocument,
    AssessmentSessionDocument,
    ConsentEventDocument,
    DailyMoodRecordDocument,
    DocumentModel,
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
from app.repositories.cloudbase_store import CloudBaseStore
from app.repositories.collection_registry import COLLECTIONS
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.protocols import (
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)

D = TypeVar("D", bound=DocumentModel)


class CloudBaseDomainDataRepository(InMemoryDomainDataRepository):
    """Overrides every public operation; no process-local business state is used.

    The base class preserves compatibility with existing service annotations.
    Queries filter by owner or business key before loading paginated results.
    """

    def __init__(self, store: CloudBaseStore) -> None:
        self.store = store

    @staticmethod
    def _parse(model: type[D], document: Mapping[str, Any]) -> D:
        try:
            return model.model_validate(document)
        except ValidationError:
            raise RepositoryUnavailable("stored document violates its schema") from None

    def _get(self, model: type[D], collection: str, document_id: str) -> D:
        return self._parse(model, self.store.get(collection, document_id))

    def _first(self, model: type[D], collection: str, where: Mapping[str, Any]) -> D | None:
        items = self.store.query(collection, where, limit=1)
        return self._parse(model, items[0]) if items else None

    def _list(
        self,
        model: type[D],
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        reverse: bool = False,
    ) -> tuple[D, ...]:
        items = [self._parse(model, item) for item in self.store.all(collection, where)]
        return tuple(
            sorted(items, key=lambda item: (item.created_at, item.document_id), reverse=reverse)
        )

    def _insert(self, collection: str, document: D) -> D:
        self.store.insert(collection, document.model_dump(by_alias=True))
        return document

    def _save(self, collection: str, document: D, expected_version: int) -> D:
        current = self.store.get(collection, document.document_id)
        if current.get("version") != expected_version:
            raise RepositoryVersionConflict(current.get("version"))
        updated = document.model_copy(
            update={"version": expected_version + 1, "updated_at": datetime.now(UTC)}
        )
        self.store.replace(collection, updated.model_dump(by_alias=True), expected_version)
        return updated

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self.store.transaction():
            yield

    def get_user(self, user_id: str) -> UserAccountDocument:
        return self._get(UserAccountDocument, "user_accounts", user_id)

    def get_user_by_auth_subject_hash(self, subject_hash: str) -> UserAccountDocument | None:
        return self._first(
            UserAccountDocument, "user_accounts", {"auth_subject_hash": subject_hash}
        )

    def create_user(self, user: UserAccountDocument) -> UserAccountDocument:
        return self._insert("user_accounts", user)

    def save_user(self, user: UserAccountDocument, *, expected_version: int) -> UserAccountDocument:
        return self._save("user_accounts", user, expected_version)

    def append_consent_event(self, consent: ConsentEventDocument) -> ConsentEventDocument:
        return self._insert("consent_records", consent)

    def list_consent_events(self, user_id: str) -> tuple[ConsentEventDocument, ...]:
        return tuple(
            sorted(
                self._list(ConsentEventDocument, "consent_records", {"user_id": user_id}),
                key=lambda x: (x.occurred_at, x.document_id),
            )
        )

    def create_identity_record(self, identity: IdentityRecordDocument) -> IdentityRecordDocument:
        return self._insert("identity_records", identity)

    def save_identity_record(
        self, identity: IdentityRecordDocument, *, expected_version: int
    ) -> IdentityRecordDocument:
        return self._save("identity_records", identity, expected_version)

    def get_identity_record(self, identity_record_id: str) -> IdentityRecordDocument:
        return self._get(IdentityRecordDocument, "identity_records", identity_record_id)

    def get_identity_record_by_user(self, user_id: str) -> IdentityRecordDocument | None:
        return self._first(IdentityRecordDocument, "identity_records", {"user_id": user_id})

    def create_anonymous_identity(
        self, anonymous_identity: AnonymousIdentityDocument
    ) -> AnonymousIdentityDocument:
        return self._insert("anonymous_identities", anonymous_identity)

    def get_anonymous_identity(self, anonymous_identity_id: str) -> AnonymousIdentityDocument:
        return self._get(AnonymousIdentityDocument, "anonymous_identities", anonymous_identity_id)

    def get_active_anonymous_identity_by_user(
        self, user_id: str
    ) -> AnonymousIdentityDocument | None:
        return self._first(
            AnonymousIdentityDocument,
            "anonymous_identities",
            {"user_id": user_id, "status": "active"},
        )

    def list_anonymous_identities(self, user_id: str) -> tuple[AnonymousIdentityDocument, ...]:
        return self._list(AnonymousIdentityDocument, "anonymous_identities", {"user_id": user_id})

    def next_consent_id(self) -> str:
        return "consent_" + uuid4().hex

    def next_identity_record_id(self) -> str:
        return "identity_record_" + uuid4().hex

    def next_anonymous_identity_id(self) -> str:
        return "anonymous_identity_" + uuid4().hex

    def get_assessment_module(self, module_code: str) -> AssessmentModuleDocument:
        result = self._first(
            AssessmentModuleDocument, "assessment_modules", {"module_code": module_code}
        )
        if result is None:
            raise RepositoryNotFound("assessment module not found")
        return result

    def replace_assessment_module(
        self, module: AssessmentModuleDocument, *, expected_version: int
    ) -> AssessmentModuleDocument:
        return self._save("assessment_modules", module, expected_version)

    def get_assessment_questionnaire(
        self, module_code: str, questionnaire_version: str
    ) -> AssessmentQuestionnaireDocument:
        result = self._first(
            AssessmentQuestionnaireDocument,
            "assessment_questionnaires",
            {"module_code": module_code, "questionnaire_version": questionnaire_version},
        )
        if result is None:
            raise RepositoryNotFound("assessment questionnaire not found")
        return result

    def create_assessment_session(
        self, session: AssessmentSessionDocument
    ) -> AssessmentSessionDocument:
        return self._insert("assessment_sessions", session)

    def get_assessment_session(self, session_id: str) -> AssessmentSessionDocument:
        return self._get(AssessmentSessionDocument, "assessment_sessions", session_id)

    def save_assessment_session(
        self, session: AssessmentSessionDocument, *, expected_version: int
    ) -> AssessmentSessionDocument:
        return self._save("assessment_sessions", session, expected_version)

    def create_assessment_result(
        self, result: AssessmentResultDocument
    ) -> AssessmentResultDocument:
        return self._insert("assessment_results", result)

    def get_assessment_result(self, result_id: str) -> AssessmentResultDocument:
        return self._get(AssessmentResultDocument, "assessment_results", result_id)

    def get_assessment_result_by_session(self, session_id: str) -> AssessmentResultDocument | None:
        return self._first(
            AssessmentResultDocument, "assessment_results", {"session_id": session_id}
        )

    def save_assessment_result(
        self, result: AssessmentResultDocument, *, expected_version: int
    ) -> AssessmentResultDocument:
        return self._save("assessment_results", result, expected_version)

    def list_assessment_results_by_session(
        self, session_id: str
    ) -> tuple[AssessmentResultDocument, ...]:
        return self._list(
            AssessmentResultDocument, "assessment_results", {"session_id": session_id}
        )

    def list_assessment_results_by_user(self, user_id: str) -> tuple[AssessmentResultDocument, ...]:
        return self._list(
            AssessmentResultDocument,
            "assessment_results",
            {"user_id": user_id, "deleted_at": None},
            reverse=True,
        )

    def create_daily_mood_record(self, record: DailyMoodRecordDocument) -> DailyMoodRecordDocument:
        return self._insert("daily_mood_records", record)

    def get_daily_mood(self, record_id: str) -> DailyMoodRecordDocument:
        return self._get(DailyMoodRecordDocument, "daily_mood_records", record_id)

    def get_daily_mood_by_user_date(
        self, user_id: str, record_date: str
    ) -> DailyMoodRecordDocument | None:
        return self._first(
            DailyMoodRecordDocument,
            "daily_mood_records",
            {"user_id": user_id, "record_date": record_date},
        )

    def list_daily_mood_records(self, user_id: str) -> tuple[DailyMoodRecordDocument, ...]:
        return tuple(
            sorted(
                self._list(
                    DailyMoodRecordDocument,
                    "daily_mood_records",
                    {"user_id": user_id, "deleted_at": None},
                ),
                key=lambda x: (x.record_date, x.created_at),
                reverse=True,
            )
        )

    def save_daily_mood_record(
        self, record: DailyMoodRecordDocument, *, expected_version: int
    ) -> DailyMoodRecordDocument:
        return self._save("daily_mood_records", record, expected_version)

    def list_available_quote_entries(self, record_date: str) -> tuple[QuoteEntryDocument, ...]:
        items = self._list(
            QuoteEntryDocument,
            "quote_entries",
            {
                "enabled": True,
                "review_status": "已启用",
                "source_kind": {"$in": ["public_domain", "project_original"]},
            },
        )
        return tuple(
            sorted(
                (
                    x
                    for x in items
                    if (x.display_from is None or x.display_from <= record_date)
                    and (x.display_until is None or x.display_until >= record_date)
                ),
                key=lambda x: (x.sort_order, x.document_id),
            )
        )

    def list_support_resources(
        self,
        environment_scope: str,
        *,
        resource_set_version: str | None = None,
        now: datetime | None = None,
    ) -> tuple[SupportResourceDocument, ...]:
        where: dict[str, Any] = {"environment_scope": environment_scope, "enabled": True}
        if resource_set_version is not None:
            where["resource_set_version"] = resource_set_version
        current = now or datetime.now(UTC)
        return tuple(
            sorted(
                (
                    x
                    for x in self._list(SupportResourceDocument, "support_resources", where)
                    if x.expires_at is None or x.expires_at > current
                ),
                key=lambda x: (x.sort_order, x.document_id),
            )
        )

    def create_safety_support_task(
        self, task: SafetySupportTaskDocument
    ) -> SafetySupportTaskDocument:
        return self._insert("safety_support_tasks", task)

    def list_safety_support_tasks(self) -> tuple[SafetySupportTaskDocument, ...]:
        return self._list(SafetySupportTaskDocument, "safety_support_tasks")

    def create_work_task(self, task: WorkTaskDocument) -> WorkTaskDocument:
        return self._insert("work_tasks", task)

    def get_work_task(self, task_id: str) -> WorkTaskDocument:
        return self._get(WorkTaskDocument, "work_tasks", task_id)

    def list_work_tasks(self) -> tuple[WorkTaskDocument, ...]:
        return self._list(WorkTaskDocument, "work_tasks", reverse=True)

    def save_work_task(self, task: WorkTaskDocument, *, expected_version: int) -> WorkTaskDocument:
        return self._save("work_tasks", task, expected_version)

    def create_treehole_post(self, post: TreeholePostDocument) -> TreeholePostDocument:
        return self._insert("treehole_posts", post)

    def get_treehole_post(self, post_id: str) -> TreeholePostDocument:
        return self._get(TreeholePostDocument, "treehole_posts", post_id)

    def save_treehole_post(
        self, post: TreeholePostDocument, *, expected_version: int
    ) -> TreeholePostDocument:
        return self._save("treehole_posts", post, expected_version)

    def list_treehole_posts(self) -> tuple[TreeholePostDocument, ...]:
        return self._list(TreeholePostDocument, "treehole_posts", reverse=True)

    def create_treehole_response(
        self, response: TreeholeResponseDocument
    ) -> TreeholeResponseDocument:
        return self._insert("treehole_responses", response)

    def get_treehole_response(self, response_id: str) -> TreeholeResponseDocument:
        return self._get(TreeholeResponseDocument, "treehole_responses", response_id)

    def save_treehole_response(
        self, response: TreeholeResponseDocument, *, expected_version: int
    ) -> TreeholeResponseDocument:
        return self._save("treehole_responses", response, expected_version)

    def list_treehole_responses(self, post_id: str) -> tuple[TreeholeResponseDocument, ...]:
        return self._list(TreeholeResponseDocument, "treehole_responses", {"post_id": post_id})

    def next_assessment_session_id(self) -> str:
        return "assessment_session_" + uuid4().hex

    def next_assessment_result_id(self) -> str:
        return "assessment_result_" + uuid4().hex

    def next_daily_mood_id(self) -> str:
        return "daily_mood_" + uuid4().hex

    def next_safety_support_task_id(self) -> str:
        return "safety_support_task_" + uuid4().hex

    def next_work_task_id(self) -> str:
        return "work_task_" + uuid4().hex

    def next_treehole_post_id(self) -> str:
        return "treehole_post_" + uuid4().hex

    def next_treehole_response_id(self) -> str:
        return "treehole_response_" + uuid4().hex

    def create_identity_access_request(
        self, request: IdentityAccessRequestDocument
    ) -> IdentityAccessRequestDocument:
        return self._insert("identity_access_requests", request)

    def get_identity_access_request(self, request_id: str) -> IdentityAccessRequestDocument:
        return self._get(IdentityAccessRequestDocument, "identity_access_requests", request_id)

    def save_identity_access_request(
        self, request: IdentityAccessRequestDocument, *, expected_version: int
    ) -> IdentityAccessRequestDocument:
        return self._save("identity_access_requests", request, expected_version)

    def next_identity_access_request_id(self) -> str:
        return "identity_access_request_" + uuid4().hex

    def list_identity_access_requests(self) -> tuple[IdentityAccessRequestDocument, ...]:
        return self._list(IdentityAccessRequestDocument, "identity_access_requests", reverse=True)

    def extra_collection(self, name: str) -> list[dict[str, Any]]:
        if name not in COLLECTIONS:
            raise ValueError("unknown business collection")
        return [
            {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in item.items()
            }
            for item in self.store.all(name)
        ]

    def append_extra_document(self, name: str, document: Mapping[str, Any]) -> None:
        if name not in COLLECTIONS:
            raise ValueError("unknown business collection")
        self.store.insert(name, dict(document))
