"""Minimal typed repository for consent and identity domain data."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.infra.database.common import RepositoryNotFound, RepositoryVersionConflict
from app.infra.database.memory.transaction import MemoryUnitOfWork
from app.infra.logger.common import traced
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


class InMemoryDomainDataRepository:
    def __init__(
        self,
        *,
        users: list[UserAccountDocument] | None = None,
        consents: list[ConsentEventDocument] | None = None,
        identities: list[IdentityRecordDocument] | None = None,
        anonymous_identities: list[AnonymousIdentityDocument] | None = None,
        assessment_modules: list[AssessmentModuleDocument] | None = None,
        assessment_questionnaires: list[AssessmentQuestionnaireDocument] | None = None,
        assessment_sessions: list[AssessmentSessionDocument] | None = None,
        assessment_results: list[AssessmentResultDocument] | None = None,
        daily_mood_records: list[DailyMoodRecordDocument] | None = None,
        quote_entries: list[QuoteEntryDocument] | None = None,
        support_resources: list[SupportResourceDocument] | None = None,
        safety_support_tasks: list[SafetySupportTaskDocument] | None = None,
        work_tasks: list[WorkTaskDocument] | None = None,
        treehole_posts: list[TreeholePostDocument] | None = None,
        treehole_responses: list[TreeholeResponseDocument] | None = None,
        identity_access_requests: list[IdentityAccessRequestDocument] | None = None,
        extra_collections: Mapping[str, list[Mapping[str, Any]]] | None = None,
    ) -> None:
        self._lock = MemoryUnitOfWork()
        self._lock.register(self)
        self._users = {user.document_id: user for user in users or []}
        self._consents = {consent.document_id: consent for consent in consents or []}
        self._identities = {identity.document_id: identity for identity in identities or []}
        self._anonymous = {
            anonymous_identity.document_id: anonymous_identity
            for anonymous_identity in anonymous_identities or []
        }
        self._assessment_modules: dict[str, AssessmentModuleDocument] = {
            module.module_code: module for module in assessment_modules or []
        }
        self._assessment_questionnaires: dict[tuple[str, str], AssessmentQuestionnaireDocument] = {
            (questionnaire.module_code, questionnaire.questionnaire_version): questionnaire
            for questionnaire in assessment_questionnaires or []
        }
        self._assessment_sessions = {
            session.document_id: session for session in assessment_sessions or []
        }
        self._assessment_results = {
            result.document_id: result for result in assessment_results or []
        }
        self._daily_moods = {record.document_id: record for record in daily_mood_records or []}
        self._quote_entries = {quote.document_id: quote for quote in quote_entries or []}
        self._support_resources = {
            resource.document_id: resource for resource in support_resources or []
        }
        self._safety_support_tasks = {task.document_id: task for task in safety_support_tasks or []}
        self._work_tasks = {task.document_id: task for task in work_tasks or []}
        self._treehole_posts = {post.document_id: post for post in treehole_posts or []}
        self._treehole_responses = {
            response.document_id: response for response in treehole_responses or []
        }
        self._identity_access_requests = {
            item.document_id: item for item in identity_access_requests or []
        }
        self._extra_collections = {
            name: [deepcopy(dict(item)) for item in items]
            for name, items in (extra_collections or {}).items()
        }
        self._identity_counter = len(self._identities)
        self._consent_counter = len(self._consents)
        self._anonymous_counter = len(self._anonymous)
        self._assessment_session_counter = len(self._assessment_sessions)
        self._assessment_result_counter = len(self._assessment_results)
        self._daily_mood_counter = len(self._daily_moods)
        self._safety_support_task_counter = len(self._safety_support_tasks)
        self._work_task_counter = len(self._work_tasks)
        self._treehole_post_counter = len(self._treehole_posts)
        self._treehole_response_counter = len(self._treehole_responses)
        self._identity_access_request_counter = len(self._identity_access_requests)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        """Run a domain write atomically across all in-memory collections."""

        async with self._lock.transaction():
            yield

    @traced
    async def get_user(self, user_id: str) -> UserAccountDocument:
        async with self._lock:
            try:
                return self._users[user_id]
            except KeyError as error:
                raise RepositoryNotFound("user not found") from error

    @traced
    async def get_user_by_auth_subject_hash(self, subject_hash: str) -> UserAccountDocument | None:
        async with self._lock:
            return next(
                (user for user in self._users.values() if user.auth_subject_hash == subject_hash),
                None,
            )

    @traced
    async def create_user(self, user: UserAccountDocument) -> UserAccountDocument:
        async with self._lock:
            if user.document_id in self._users:
                raise RepositoryVersionConflict(self._users[user.document_id].version)
            if (await self.get_user_by_auth_subject_hash(user.auth_subject_hash)) is not None:
                raise RepositoryVersionConflict(1)
            self._users[user.document_id] = user
            return user

    @traced
    async def save_user(
        self, user: UserAccountDocument, *, expected_version: int
    ) -> UserAccountDocument:
        async with self._lock:
            current = await self.get_user(user.document_id)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = user.model_copy(
                update={
                    "updated_at": datetime.now(UTC),
                    "version": current.version + 1,
                }
            )
            self._users[user.document_id] = updated
            return updated

    @traced
    async def append_consent_event(self, consent: ConsentEventDocument) -> ConsentEventDocument:
        async with self._lock:
            self._consents[consent.document_id] = consent
            return consent

    @traced
    async def list_consent_events(self, user_id: str) -> tuple[ConsentEventDocument, ...]:
        async with self._lock:
            events = [event for event in self._consents.values() if event.user_id == user_id]
            events.sort(key=lambda event: (event.occurred_at, event.document_id))
            return tuple(events)

    @traced
    async def create_identity_record(
        self, identity: IdentityRecordDocument
    ) -> IdentityRecordDocument:
        async with self._lock:
            self._identities[identity.document_id] = identity
            return identity

    @traced
    async def save_identity_record(
        self,
        identity: IdentityRecordDocument,
        *,
        expected_version: int,
    ) -> IdentityRecordDocument:
        async with self._lock:
            current = await self.get_identity_record(identity.document_id)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = identity.model_copy(
                update={
                    "updated_at": datetime.now(UTC),
                    "version": current.version + 1,
                }
            )
            self._identities[identity.document_id] = updated
            return updated

    @traced
    async def get_identity_record(self, identity_record_id: str) -> IdentityRecordDocument:
        async with self._lock:
            try:
                return self._identities[identity_record_id]
            except KeyError as error:
                raise RepositoryNotFound("identity record not found") from error

    @traced
    async def get_identity_record_by_user(self, user_id: str) -> IdentityRecordDocument | None:
        async with self._lock:
            for record in self._identities.values():
                if record.user_id == user_id:
                    return record
            return None

    @traced
    async def create_anonymous_identity(
        self,
        anonymous_identity: AnonymousIdentityDocument,
    ) -> AnonymousIdentityDocument:
        async with self._lock:
            self._anonymous[anonymous_identity.document_id] = anonymous_identity
            return anonymous_identity

    @traced
    async def get_anonymous_identity(self, anonymous_identity_id: str) -> AnonymousIdentityDocument:
        async with self._lock:
            try:
                return self._anonymous[anonymous_identity_id]
            except KeyError as error:
                raise RepositoryNotFound("anonymous identity not found") from error

    @traced
    async def get_active_anonymous_identity_by_user(
        self,
        user_id: str,
    ) -> AnonymousIdentityDocument | None:
        async with self._lock:
            for identity in self._anonymous.values():
                if identity.user_id == user_id and identity.status == "active":
                    return identity
            return None

    @traced
    async def list_anonymous_identities(
        self, user_id: str
    ) -> tuple[AnonymousIdentityDocument, ...]:
        async with self._lock:
            identities = [
                identity for identity in self._anonymous.values() if identity.user_id == user_id
            ]
            identities.sort(key=lambda identity: (identity.created_at, identity.document_id))
            return tuple(identities)

    @traced
    async def next_consent_id(self) -> str:
        async with self._lock:
            self._consent_counter += 1
            return f"consent_{self._consent_counter:04d}"

    @traced
    async def next_identity_record_id(self) -> str:
        async with self._lock:
            self._identity_counter += 1
            return f"identity_{self._identity_counter:04d}"

    @traced
    async def next_anonymous_identity_id(self) -> str:
        async with self._lock:
            self._anonymous_counter += 1
            return f"anonymous_{self._anonymous_counter:04d}"

    @traced
    async def get_assessment_module(self, module_code: str) -> AssessmentModuleDocument:
        async with self._lock:
            try:
                return self._assessment_modules[module_code]
            except KeyError as error:
                raise RepositoryNotFound("assessment module not found") from error

    @traced
    async def replace_assessment_module(
        self,
        module: AssessmentModuleDocument,
        *,
        expected_version: int,
    ) -> AssessmentModuleDocument:
        async with self._lock:
            current = await self.get_assessment_module(module.module_code)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = module.model_copy(
                update={"updated_at": datetime.now(UTC), "version": current.version + 1}
            )
            self._assessment_modules[module.module_code] = updated
            return updated

    @traced
    async def get_assessment_questionnaire(
        self,
        module_code: str,
        questionnaire_version: str,
    ) -> AssessmentQuestionnaireDocument:
        async with self._lock:
            key = (module_code, questionnaire_version)
            try:
                return self._assessment_questionnaires[key]
            except KeyError as error:
                raise RepositoryNotFound("assessment questionnaire not found") from error

    @traced
    async def create_assessment_session(
        self, session: AssessmentSessionDocument
    ) -> AssessmentSessionDocument:
        async with self._lock:
            self._assessment_sessions[session.document_id] = session
            return session

    @traced
    async def get_assessment_session(self, session_id: str) -> AssessmentSessionDocument:
        async with self._lock:
            try:
                return self._assessment_sessions[session_id]
            except KeyError as error:
                raise RepositoryNotFound("assessment session not found") from error

    @traced
    async def save_assessment_session(
        self,
        session: AssessmentSessionDocument,
        *,
        expected_version: int,
    ) -> AssessmentSessionDocument:
        async with self._lock:
            current = await self.get_assessment_session(session.document_id)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = session.model_copy(
                update={"updated_at": datetime.now(UTC), "version": current.version + 1}
            )
            self._assessment_sessions[session.document_id] = updated
            return updated

    @traced
    async def create_assessment_result(
        self,
        result: AssessmentResultDocument,
    ) -> AssessmentResultDocument:
        async with self._lock:
            if (await self.get_assessment_result_by_session(result.session_id)) is not None:
                raise RepositoryVersionConflict(1)
            self._assessment_results[result.document_id] = result
            return result

    @traced
    async def get_assessment_result(self, result_id: str) -> AssessmentResultDocument:
        async with self._lock:
            try:
                return self._assessment_results[result_id]
            except KeyError as error:
                raise RepositoryNotFound("assessment result not found") from error

    @traced
    async def get_assessment_result_by_session(
        self,
        session_id: str,
    ) -> AssessmentResultDocument | None:
        async with self._lock:
            for result in self._assessment_results.values():
                if result.session_id == session_id:
                    return result
            return None

    @traced
    async def save_assessment_result(
        self,
        result: AssessmentResultDocument,
        *,
        expected_version: int,
    ) -> AssessmentResultDocument:
        async with self._lock:
            current = await self.get_assessment_result(result.document_id)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = result.model_copy(
                update={"updated_at": datetime.now(UTC), "version": current.version + 1}
            )
            self._assessment_results[result.document_id] = updated
            return updated

    @traced
    async def list_assessment_results_by_session(
        self,
        session_id: str,
    ) -> tuple[AssessmentResultDocument, ...]:
        async with self._lock:
            results = [
                result
                for result in self._assessment_results.values()
                if result.session_id == session_id
            ]
            results.sort(key=lambda result: (result.created_at, result.document_id))
            return tuple(results)

    @traced
    async def list_assessment_results_by_user(
        self,
        user_id: str,
    ) -> tuple[AssessmentResultDocument, ...]:
        async with self._lock:
            results = [
                result
                for result in self._assessment_results.values()
                if result.user_id == user_id and result.deleted_at is None
            ]
            results.sort(key=lambda result: (result.created_at, result.document_id), reverse=True)
            return tuple(results)

    @traced
    async def create_daily_mood_record(
        self,
        record: DailyMoodRecordDocument,
    ) -> DailyMoodRecordDocument:
        async with self._lock:
            existing = await self.get_daily_mood_by_user_date(record.user_id, record.record_date)
            if existing is not None:
                raise RepositoryVersionConflict(existing.version)
            self._daily_moods[record.document_id] = record
            return record

    @traced
    async def get_daily_mood(self, record_id: str) -> DailyMoodRecordDocument:
        async with self._lock:
            try:
                return self._daily_moods[record_id]
            except KeyError as error:
                raise RepositoryNotFound("daily mood record not found") from error

    @traced
    async def get_daily_mood_by_user_date(
        self,
        user_id: str,
        record_date: str,
    ) -> DailyMoodRecordDocument | None:
        async with self._lock:
            for record in self._daily_moods.values():
                if record.user_id == user_id and record.record_date == record_date:
                    return record
            return None

    @traced
    async def list_daily_mood_records(self, user_id: str) -> tuple[DailyMoodRecordDocument, ...]:
        async with self._lock:
            records = [
                record
                for record in self._daily_moods.values()
                if record.user_id == user_id and record.deleted_at is None
            ]
            records.sort(key=lambda record: (record.record_date, record.created_at), reverse=True)
            return tuple(records)

    @traced
    async def save_daily_mood_record(
        self,
        record: DailyMoodRecordDocument,
        *,
        expected_version: int,
    ) -> DailyMoodRecordDocument:
        async with self._lock:
            current = await self.get_daily_mood(record.document_id)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = record.model_copy(
                update={"updated_at": datetime.now(UTC), "version": current.version + 1}
            )
            self._daily_moods[record.document_id] = updated
            return updated

    @traced
    async def list_available_quote_entries(
        self, record_date: str
    ) -> tuple[QuoteEntryDocument, ...]:
        async with self._lock:
            quotes = [
                quote
                for quote in self._quote_entries.values()
                if quote.enabled
                and quote.review_status == "已启用"
                and quote.source_kind in {"public_domain", "project_original"}
                and (quote.display_from is None or quote.display_from <= record_date)
                and (quote.display_until is None or quote.display_until >= record_date)
            ]
            quotes.sort(key=lambda quote: (quote.sort_order, quote.document_id))
            return tuple(quotes)

    @traced
    async def list_support_resources(
        self,
        environment_scope: str,
        *,
        resource_set_version: str | None = None,
        now: datetime | None = None,
    ) -> tuple[SupportResourceDocument, ...]:
        async with self._lock:
            current = now or datetime.now(UTC)
            resources = [
                resource
                for resource in self._support_resources.values()
                if resource.environment_scope == environment_scope
                and resource.enabled
                and (
                    resource_set_version is None
                    or resource.resource_set_version == resource_set_version
                )
                and (resource.expires_at is None or resource.expires_at > current)
            ]
            resources.sort(key=lambda resource: (resource.sort_order, resource.document_id))
            return tuple(resources)

    @traced
    async def create_safety_support_task(
        self,
        task: SafetySupportTaskDocument,
    ) -> SafetySupportTaskDocument:
        async with self._lock:
            self._safety_support_tasks[task.document_id] = task
            return task

    @traced
    async def list_safety_support_tasks(self) -> tuple[SafetySupportTaskDocument, ...]:
        async with self._lock:
            tasks = list(self._safety_support_tasks.values())
            tasks.sort(key=lambda task: (task.created_at, task.document_id))
            return tuple(tasks)

    @traced
    async def create_work_task(self, task: WorkTaskDocument) -> WorkTaskDocument:
        async with self._lock:
            self._work_tasks[task.document_id] = task
            return task

    @traced
    async def get_work_task(self, task_id: str) -> WorkTaskDocument:
        async with self._lock:
            try:
                return self._work_tasks[task_id]
            except KeyError as error:
                raise RepositoryNotFound("work task not found") from error

    @traced
    async def list_work_tasks(self) -> tuple[WorkTaskDocument, ...]:
        async with self._lock:
            tasks = list(self._work_tasks.values())
            tasks.sort(key=lambda task: (task.created_at, task.document_id), reverse=True)
            return tuple(tasks)

    @traced
    async def save_work_task(
        self, task: WorkTaskDocument, *, expected_version: int
    ) -> WorkTaskDocument:
        async with self._lock:
            current = await self.get_work_task(task.document_id)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = task.model_copy(
                update={"updated_at": datetime.now(UTC), "version": current.version + 1}
            )
            self._work_tasks[task.document_id] = updated
            return updated

    @traced
    async def create_treehole_post(self, post: TreeholePostDocument) -> TreeholePostDocument:
        async with self._lock:
            self._treehole_posts[post.document_id] = post
            return post

    @traced
    async def get_treehole_post(self, post_id: str) -> TreeholePostDocument:
        async with self._lock:
            try:
                return self._treehole_posts[post_id]
            except KeyError as error:
                raise RepositoryNotFound("treehole post not found") from error

    @traced
    async def save_treehole_post(
        self,
        post: TreeholePostDocument,
        *,
        expected_version: int,
    ) -> TreeholePostDocument:
        async with self._lock:
            current = await self.get_treehole_post(post.document_id)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = post.model_copy(
                update={"updated_at": datetime.now(UTC), "version": current.version + 1}
            )
            self._treehole_posts[post.document_id] = updated
            return updated

    @traced
    async def list_treehole_posts(self) -> tuple[TreeholePostDocument, ...]:
        async with self._lock:
            posts = list(self._treehole_posts.values())
            posts.sort(key=lambda post: (post.created_at, post.document_id), reverse=True)
            return tuple(posts)

    @traced
    async def create_treehole_response(
        self, response: TreeholeResponseDocument
    ) -> TreeholeResponseDocument:
        async with self._lock:
            self._treehole_responses[response.document_id] = response
            return response

    @traced
    async def get_treehole_response(self, response_id: str) -> TreeholeResponseDocument:
        async with self._lock:
            try:
                return self._treehole_responses[response_id]
            except KeyError as error:
                raise RepositoryNotFound("treehole response not found") from error

    @traced
    async def save_treehole_response(
        self,
        response: TreeholeResponseDocument,
        *,
        expected_version: int,
    ) -> TreeholeResponseDocument:
        async with self._lock:
            current = await self.get_treehole_response(response.document_id)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = response.model_copy(
                update={"updated_at": datetime.now(UTC), "version": current.version + 1}
            )
            self._treehole_responses[response.document_id] = updated
            return updated

    @traced
    async def list_treehole_responses(self, post_id: str) -> tuple[TreeholeResponseDocument, ...]:
        async with self._lock:
            responses = [
                response
                for response in self._treehole_responses.values()
                if response.post_id == post_id
            ]
            responses.sort(key=lambda response: (response.created_at, response.document_id))
            return tuple(responses)

    @traced
    async def next_assessment_session_id(self) -> str:
        async with self._lock:
            self._assessment_session_counter += 1
            return f"assessment_session_{self._assessment_session_counter:04d}"

    @traced
    async def next_assessment_result_id(self) -> str:
        async with self._lock:
            self._assessment_result_counter += 1
            return f"assessment_result_{self._assessment_result_counter:04d}"

    @traced
    async def next_daily_mood_id(self) -> str:
        async with self._lock:
            self._daily_mood_counter += 1
            return f"daily_mood_{self._daily_mood_counter:04d}"

    @traced
    async def next_safety_support_task_id(self) -> str:
        async with self._lock:
            self._safety_support_task_counter += 1
            return f"safety_support_task_{self._safety_support_task_counter:04d}"

    @traced
    async def next_work_task_id(self) -> str:
        async with self._lock:
            self._work_task_counter += 1
            return f"work_task_{self._work_task_counter:04d}"

    @traced
    async def next_treehole_post_id(self) -> str:
        async with self._lock:
            self._treehole_post_counter += 1
            return f"treehole_post_{self._treehole_post_counter:04d}"

    @traced
    async def next_treehole_response_id(self) -> str:
        async with self._lock:
            self._treehole_response_counter += 1
            return f"treehole_response_{self._treehole_response_counter:04d}"

    @traced
    async def create_identity_access_request(
        self, request: IdentityAccessRequestDocument
    ) -> IdentityAccessRequestDocument:
        async with self._lock:
            self._identity_access_requests[request.document_id] = request
            return request

    @traced
    async def get_identity_access_request(self, request_id: str) -> IdentityAccessRequestDocument:
        async with self._lock:
            try:
                return self._identity_access_requests[request_id]
            except KeyError as error:
                raise RepositoryNotFound("identity access request not found") from error

    @traced
    async def save_identity_access_request(
        self,
        request: IdentityAccessRequestDocument,
        *,
        expected_version: int,
    ) -> IdentityAccessRequestDocument:
        async with self._lock:
            current = await self.get_identity_access_request(request.document_id)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = request.model_copy(
                update={"updated_at": datetime.now(UTC), "version": current.version + 1}
            )
            self._identity_access_requests[request.document_id] = updated
            return updated

    @traced
    async def next_identity_access_request_id(self) -> str:
        async with self._lock:
            self._identity_access_request_counter += 1
            return f"identity_access_request_{self._identity_access_request_counter:04d}"

    @traced
    async def list_identity_access_requests(self) -> tuple[IdentityAccessRequestDocument, ...]:
        async with self._lock:
            items = list(self._identity_access_requests.values())
            items.sort(key=lambda item: (item.created_at, item.document_id), reverse=True)
            return tuple(items)

    @traced
    async def extra_collection(self, name: str) -> list[dict[str, Any]]:
        async with self._lock:
            if name == "work_tasks":
                return [
                    task.model_dump(by_alias=True, mode="json")
                    for task in sorted(
                        self._work_tasks.values(),
                        key=lambda task: (task.created_at, task.document_id),
                    )
                ]
            if name == "safety_support_tasks":
                return [
                    task.model_dump(by_alias=True, mode="json")
                    for task in sorted(
                        self._safety_support_tasks.values(),
                        key=lambda task: (task.created_at, task.document_id),
                    )
                ]
            if name == "daily_mood_records":
                return [
                    record.model_dump(by_alias=True, mode="json")
                    for record in sorted(
                        self._daily_moods.values(),
                        key=lambda record: (record.record_date, record.document_id),
                    )
                ]
            if name == "quote_entries":
                return [
                    quote.model_dump(by_alias=True, mode="json")
                    for quote in sorted(
                        self._quote_entries.values(),
                        key=lambda quote: (quote.sort_order, quote.document_id),
                    )
                ]
            if name == "support_resources":
                return [
                    resource.model_dump(by_alias=True, mode="json")
                    for resource in sorted(
                        self._support_resources.values(),
                        key=lambda resource: (resource.sort_order, resource.document_id),
                    )
                ]
            if name == "treehole_posts":
                documents = [
                    post.model_dump(by_alias=True, mode="json")
                    for post in sorted(
                        self._treehole_posts.values(),
                        key=lambda post: (post.created_at, post.document_id),
                    )
                ]
                return documents or deepcopy(self._extra_collections.get(name, []))
            if name == "treehole_responses":
                return [
                    response.model_dump(by_alias=True, mode="json")
                    for response in sorted(
                        self._treehole_responses.values(),
                        key=lambda response: (response.created_at, response.document_id),
                    )
                ]
            return deepcopy(self._extra_collections.get(name, []))

    @traced
    async def append_extra_document(self, name: str, document: Mapping[str, Any]) -> None:
        async with self._lock:
            self._extra_collections.setdefault(name, []).append(deepcopy(dict(document)))
