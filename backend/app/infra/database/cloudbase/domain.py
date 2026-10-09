"""CloudBase implementation of the existing typed domain repository contract."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import ValidationError

from app.infra.database.cloudbase.client import CloudBaseStore
from app.infra.database.collections import COLLECTIONS
from app.infra.database.common import (
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)
from app.infra.logger.common import traced
from app.models.v2.documents import (
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

D = TypeVar("D", bound=DocumentModel)


class CloudBaseDomainDataRepository:
    """Typed domain port backed only by the shared asynchronous CloudBase store."""

    def __init__(self, store: CloudBaseStore) -> None:
        self.store = store

    @staticmethod
    @traced
    def _parse(model: type[D], document: Mapping[str, Any]) -> D:
        try:
            return model.model_validate(document)
        except ValidationError:
            raise RepositoryUnavailable("stored document violates its schema") from None

    @traced
    async def _get(self, model: type[D], collection: str, document_id: str) -> D:
        return self._parse(model, (await self.store.get(collection, document_id)))

    @traced
    async def _first(self, model: type[D], collection: str, where: Mapping[str, Any]) -> D | None:
        items = await self.store.query(collection, where, limit=1)
        return self._parse(model, items[0]) if items else None

    @traced
    async def _list(
        self,
        model: type[D],
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        reverse: bool = False,
    ) -> tuple[D, ...]:
        items = [self._parse(model, item) for item in (await self.store.all(collection, where))]
        return tuple(
            sorted(items, key=lambda item: (item.created_at, item.document_id), reverse=reverse)
        )

    @traced
    async def _insert(self, collection: str, document: D) -> D:
        (await self.store.insert(collection, document.model_dump(by_alias=True)))
        return document

    @traced
    async def _save(self, collection: str, document: D, expected_version: int) -> D:
        current = await self.store.get(collection, document.document_id)
        if current.get("version") != expected_version:
            raise RepositoryVersionConflict(current.get("version"))
        updated = document.model_copy(
            update={"version": expected_version + 1, "updated_at": datetime.now(UTC)}
        )
        (await self.store.replace(collection, updated.model_dump(by_alias=True), expected_version))
        return updated

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        async with self.store.transaction():
            yield

    @traced
    async def get_user(self, user_id: str) -> UserAccountDocument:
        return await self._get(UserAccountDocument, "user_accounts", user_id)

    @traced
    async def get_user_by_auth_subject_hash(self, subject_hash: str) -> UserAccountDocument | None:
        return await self._first(
            UserAccountDocument, "user_accounts", {"auth_subject_hash": subject_hash}
        )

    @traced
    async def create_user(self, user: UserAccountDocument) -> UserAccountDocument:
        return await self._insert("user_accounts", user)

    @traced
    async def save_user(
        self, user: UserAccountDocument, *, expected_version: int
    ) -> UserAccountDocument:
        return await self._save("user_accounts", user, expected_version)

    @traced
    async def append_consent_event(self, consent: ConsentEventDocument) -> ConsentEventDocument:
        return await self._insert("consent_records", consent)

    @traced
    async def list_consent_events(self, user_id: str) -> tuple[ConsentEventDocument, ...]:
        return tuple(
            sorted(
                (await self._list(ConsentEventDocument, "consent_records", {"user_id": user_id})),
                key=lambda x: (x.occurred_at, x.document_id),
            )
        )

    @traced
    async def create_identity_record(
        self, identity: IdentityRecordDocument
    ) -> IdentityRecordDocument:
        return await self._insert("identity_records", identity)

    @traced
    async def save_identity_record(
        self, identity: IdentityRecordDocument, *, expected_version: int
    ) -> IdentityRecordDocument:
        return await self._save("identity_records", identity, expected_version)

    @traced
    async def get_identity_record(self, identity_record_id: str) -> IdentityRecordDocument:
        return await self._get(IdentityRecordDocument, "identity_records", identity_record_id)

    @traced
    async def get_identity_record_by_user(self, user_id: str) -> IdentityRecordDocument | None:
        return await self._first(IdentityRecordDocument, "identity_records", {"user_id": user_id})

    @traced
    async def create_anonymous_identity(
        self, anonymous_identity: AnonymousIdentityDocument
    ) -> AnonymousIdentityDocument:
        return await self._insert("anonymous_identities", anonymous_identity)

    @traced
    async def get_anonymous_identity(self, anonymous_identity_id: str) -> AnonymousIdentityDocument:
        return await self._get(
            AnonymousIdentityDocument, "anonymous_identities", anonymous_identity_id
        )

    @traced
    async def get_active_anonymous_identity_by_user(
        self, user_id: str
    ) -> AnonymousIdentityDocument | None:
        return await self._first(
            AnonymousIdentityDocument,
            "anonymous_identities",
            {"user_id": user_id, "status": "active"},
        )

    @traced
    async def list_anonymous_identities(
        self, user_id: str
    ) -> tuple[AnonymousIdentityDocument, ...]:
        return await self._list(
            AnonymousIdentityDocument, "anonymous_identities", {"user_id": user_id}
        )

    @traced
    async def next_consent_id(self) -> str:
        return "consent_" + uuid4().hex

    @traced
    async def next_identity_record_id(self) -> str:
        return "identity_record_" + uuid4().hex

    @traced
    async def next_anonymous_identity_id(self) -> str:
        return "anonymous_identity_" + uuid4().hex

    @traced
    async def get_assessment_module(self, module_code: str) -> AssessmentModuleDocument:
        result = await self._first(
            AssessmentModuleDocument, "assessment_modules", {"module_code": module_code}
        )
        if result is None:
            raise RepositoryNotFound("assessment module not found")
        return result

    @traced
    async def replace_assessment_module(
        self, module: AssessmentModuleDocument, *, expected_version: int
    ) -> AssessmentModuleDocument:
        return await self._save("assessment_modules", module, expected_version)

    @traced
    async def get_assessment_questionnaire(
        self, module_code: str, questionnaire_version: str
    ) -> AssessmentQuestionnaireDocument:
        result = await self._first(
            AssessmentQuestionnaireDocument,
            "assessment_questionnaires",
            {"module_code": module_code, "questionnaire_version": questionnaire_version},
        )
        if result is None:
            raise RepositoryNotFound("assessment questionnaire not found")
        return result

    @traced
    async def create_assessment_session(
        self, session: AssessmentSessionDocument
    ) -> AssessmentSessionDocument:
        return await self._insert("assessment_sessions", session)

    @traced
    async def get_assessment_session(self, session_id: str) -> AssessmentSessionDocument:
        return await self._get(AssessmentSessionDocument, "assessment_sessions", session_id)

    @traced
    async def save_assessment_session(
        self, session: AssessmentSessionDocument, *, expected_version: int
    ) -> AssessmentSessionDocument:
        return await self._save("assessment_sessions", session, expected_version)

    @traced
    async def create_assessment_result(
        self, result: AssessmentResultDocument
    ) -> AssessmentResultDocument:
        return await self._insert("assessment_results", result)

    @traced
    async def get_assessment_result(self, result_id: str) -> AssessmentResultDocument:
        return await self._get(AssessmentResultDocument, "assessment_results", result_id)

    @traced
    async def get_assessment_result_by_session(
        self, session_id: str
    ) -> AssessmentResultDocument | None:
        return await self._first(
            AssessmentResultDocument, "assessment_results", {"session_id": session_id}
        )

    @traced
    async def save_assessment_result(
        self, result: AssessmentResultDocument, *, expected_version: int
    ) -> AssessmentResultDocument:
        return await self._save("assessment_results", result, expected_version)

    @traced
    async def list_assessment_results_by_session(
        self, session_id: str
    ) -> tuple[AssessmentResultDocument, ...]:
        return await self._list(
            AssessmentResultDocument, "assessment_results", {"session_id": session_id}
        )

    @traced
    async def list_assessment_results_by_user(
        self, user_id: str
    ) -> tuple[AssessmentResultDocument, ...]:
        return await self._list(
            AssessmentResultDocument,
            "assessment_results",
            {"user_id": user_id, "deleted_at": None},
            reverse=True,
        )

    @traced
    async def create_daily_mood_record(
        self, record: DailyMoodRecordDocument
    ) -> DailyMoodRecordDocument:
        return await self._insert("daily_mood_records", record)

    @traced
    async def get_daily_mood(self, record_id: str) -> DailyMoodRecordDocument:
        return await self._get(DailyMoodRecordDocument, "daily_mood_records", record_id)

    @traced
    async def get_daily_mood_by_user_date(
        self, user_id: str, record_date: str
    ) -> DailyMoodRecordDocument | None:
        return await self._first(
            DailyMoodRecordDocument,
            "daily_mood_records",
            {"user_id": user_id, "record_date": record_date},
        )

    @traced
    async def list_daily_mood_records(self, user_id: str) -> tuple[DailyMoodRecordDocument, ...]:
        return tuple(
            sorted(
                (
                    await self._list(
                        DailyMoodRecordDocument,
                        "daily_mood_records",
                        {"user_id": user_id, "deleted_at": None},
                    )
                ),
                key=lambda x: (x.record_date, x.created_at),
                reverse=True,
            )
        )

    @traced
    async def save_daily_mood_record(
        self, record: DailyMoodRecordDocument, *, expected_version: int
    ) -> DailyMoodRecordDocument:
        return await self._save("daily_mood_records", record, expected_version)

    @traced
    async def list_available_quote_entries(
        self, record_date: str
    ) -> tuple[QuoteEntryDocument, ...]:
        items = await self._list(
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

    @traced
    async def list_support_resources(
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
                [
                    x
                    for x in (await self._list(SupportResourceDocument, "support_resources", where))
                    if x.expires_at is None or x.expires_at > current
                ],
                key=lambda x: (x.sort_order, x.document_id),
            )
        )

    @traced
    async def create_safety_support_task(
        self, task: SafetySupportTaskDocument
    ) -> SafetySupportTaskDocument:
        return await self._insert("safety_support_tasks", task)

    @traced
    async def list_safety_support_tasks(self) -> tuple[SafetySupportTaskDocument, ...]:
        return await self._list(SafetySupportTaskDocument, "safety_support_tasks")

    @traced
    async def create_work_task(self, task: WorkTaskDocument) -> WorkTaskDocument:
        return await self._insert("work_tasks", task)

    @traced
    async def get_work_task(self, task_id: str) -> WorkTaskDocument:
        return await self._get(WorkTaskDocument, "work_tasks", task_id)

    @traced
    async def list_work_tasks(self) -> tuple[WorkTaskDocument, ...]:
        return await self._list(WorkTaskDocument, "work_tasks", reverse=True)

    @traced
    async def save_work_task(
        self, task: WorkTaskDocument, *, expected_version: int
    ) -> WorkTaskDocument:
        return await self._save("work_tasks", task, expected_version)

    @traced
    async def create_treehole_post(self, post: TreeholePostDocument) -> TreeholePostDocument:
        return await self._insert("treehole_posts", post)

    @traced
    async def get_treehole_post(self, post_id: str) -> TreeholePostDocument:
        return await self._get(TreeholePostDocument, "treehole_posts", post_id)

    @traced
    async def save_treehole_post(
        self, post: TreeholePostDocument, *, expected_version: int
    ) -> TreeholePostDocument:
        return await self._save("treehole_posts", post, expected_version)

    @traced
    async def list_treehole_posts(self) -> tuple[TreeholePostDocument, ...]:
        return await self._list(TreeholePostDocument, "treehole_posts", reverse=True)

    @traced
    async def create_treehole_response(
        self, response: TreeholeResponseDocument
    ) -> TreeholeResponseDocument:
        return await self._insert("treehole_responses", response)

    @traced
    async def get_treehole_response(self, response_id: str) -> TreeholeResponseDocument:
        return await self._get(TreeholeResponseDocument, "treehole_responses", response_id)

    @traced
    async def save_treehole_response(
        self, response: TreeholeResponseDocument, *, expected_version: int
    ) -> TreeholeResponseDocument:
        return await self._save("treehole_responses", response, expected_version)

    @traced
    async def list_treehole_responses(self, post_id: str) -> tuple[TreeholeResponseDocument, ...]:
        return await self._list(
            TreeholeResponseDocument, "treehole_responses", {"post_id": post_id}
        )

    @traced
    async def next_assessment_session_id(self) -> str:
        return "assessment_session_" + uuid4().hex

    @traced
    async def next_assessment_result_id(self) -> str:
        return "assessment_result_" + uuid4().hex

    @traced
    async def next_daily_mood_id(self) -> str:
        return "daily_mood_" + uuid4().hex

    @traced
    async def next_safety_support_task_id(self) -> str:
        return "safety_support_task_" + uuid4().hex

    @traced
    async def next_work_task_id(self) -> str:
        return "work_task_" + uuid4().hex

    @traced
    async def next_treehole_post_id(self) -> str:
        return "treehole_post_" + uuid4().hex

    @traced
    async def next_treehole_response_id(self) -> str:
        return "treehole_response_" + uuid4().hex

    @traced
    async def create_identity_access_request(
        self, request: IdentityAccessRequestDocument
    ) -> IdentityAccessRequestDocument:
        return await self._insert("identity_access_requests", request)

    @traced
    async def get_identity_access_request(self, request_id: str) -> IdentityAccessRequestDocument:
        return await self._get(
            IdentityAccessRequestDocument, "identity_access_requests", request_id
        )

    @traced
    async def save_identity_access_request(
        self, request: IdentityAccessRequestDocument, *, expected_version: int
    ) -> IdentityAccessRequestDocument:
        return await self._save("identity_access_requests", request, expected_version)

    @traced
    async def next_identity_access_request_id(self) -> str:
        return "identity_access_request_" + uuid4().hex

    @traced
    async def list_identity_access_requests(self) -> tuple[IdentityAccessRequestDocument, ...]:
        return await self._list(
            IdentityAccessRequestDocument, "identity_access_requests", reverse=True
        )

    @traced
    async def extra_collection(self, name: str) -> list[dict[str, Any]]:
        if name not in COLLECTIONS:
            raise ValueError("unknown business collection")
        return [
            {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in item.items()
            }
            for item in (await self.store.all(name))
        ]

    @traced
    async def append_extra_document(self, name: str, document: Mapping[str, Any]) -> None:
        if name not in COLLECTIONS:
            raise ValueError("unknown business collection")
        (await self.store.insert(name, dict(document)))
