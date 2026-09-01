"""Minimal typed repository for consent and identity domain data."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from app.domain.models import (
    AnonymousIdentityDocument,
    AssessmentModuleDocument,
    AssessmentQuestionnaireDocument,
    AssessmentResultDocument,
    AssessmentSessionDocument,
    ConsentEventDocument,
    IdentityRecordDocument,
    SafetySupportTaskDocument,
    SupportResourceDocument,
    UserAccountDocument,
    WorkTaskDocument,
)
from app.repositories.protocols import RepositoryNotFound, RepositoryVersionConflict


@dataclass(frozen=True, slots=True)
class _DomainDataSnapshot:
    users: dict[str, UserAccountDocument]
    consents: dict[str, ConsentEventDocument]
    identities: dict[str, IdentityRecordDocument]
    anonymous: dict[str, AnonymousIdentityDocument]
    assessment_modules: dict[str, AssessmentModuleDocument]
    assessment_questionnaires: dict[tuple[str, str], AssessmentQuestionnaireDocument]
    assessment_sessions: dict[str, AssessmentSessionDocument]
    assessment_results: dict[str, AssessmentResultDocument]
    support_resources: dict[str, SupportResourceDocument]
    safety_support_tasks: dict[str, SafetySupportTaskDocument]
    work_tasks: dict[str, WorkTaskDocument]
    extra_collections: dict[str, list[dict[str, Any]]]
    identity_counter: int
    consent_counter: int
    anonymous_counter: int
    assessment_session_counter: int
    assessment_result_counter: int
    safety_support_task_counter: int
    work_task_counter: int


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
        support_resources: list[SupportResourceDocument] | None = None,
        safety_support_tasks: list[SafetySupportTaskDocument] | None = None,
        work_tasks: list[WorkTaskDocument] | None = None,
        extra_collections: Mapping[str, list[Mapping[str, Any]]] | None = None,
    ) -> None:
        self._lock = RLock()
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
        self._support_resources = {
            resource.document_id: resource for resource in support_resources or []
        }
        self._safety_support_tasks = {task.document_id: task for task in safety_support_tasks or []}
        self._work_tasks = {task.document_id: task for task in work_tasks or []}
        self._extra_collections = {
            name: [deepcopy(dict(item)) for item in items]
            for name, items in (extra_collections or {}).items()
        }
        self._identity_counter = len(self._identities)
        self._consent_counter = len(self._consents)
        self._anonymous_counter = len(self._anonymous)
        self._assessment_session_counter = len(self._assessment_sessions)
        self._assessment_result_counter = len(self._assessment_results)
        self._safety_support_task_counter = len(self._safety_support_tasks)
        self._work_task_counter = len(self._work_tasks)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Run a domain write atomically across all in-memory collections."""

        with self._lock:
            snapshot = self._snapshot()
            try:
                yield
            except BaseException:
                self._restore(snapshot)
                raise

    def _snapshot(self) -> _DomainDataSnapshot:
        return _DomainDataSnapshot(
            users=deepcopy(self._users),
            consents=deepcopy(self._consents),
            identities=deepcopy(self._identities),
            anonymous=deepcopy(self._anonymous),
            assessment_modules=deepcopy(self._assessment_modules),
            assessment_questionnaires=deepcopy(self._assessment_questionnaires),
            assessment_sessions=deepcopy(self._assessment_sessions),
            assessment_results=deepcopy(self._assessment_results),
            support_resources=deepcopy(self._support_resources),
            safety_support_tasks=deepcopy(self._safety_support_tasks),
            work_tasks=deepcopy(self._work_tasks),
            extra_collections=deepcopy(self._extra_collections),
            identity_counter=self._identity_counter,
            consent_counter=self._consent_counter,
            anonymous_counter=self._anonymous_counter,
            assessment_session_counter=self._assessment_session_counter,
            assessment_result_counter=self._assessment_result_counter,
            safety_support_task_counter=self._safety_support_task_counter,
            work_task_counter=self._work_task_counter,
        )

    def _restore(self, snapshot: _DomainDataSnapshot) -> None:
        self._users = snapshot.users
        self._consents = snapshot.consents
        self._identities = snapshot.identities
        self._anonymous = snapshot.anonymous
        self._assessment_modules = snapshot.assessment_modules
        self._assessment_questionnaires = snapshot.assessment_questionnaires
        self._assessment_sessions = snapshot.assessment_sessions
        self._assessment_results = snapshot.assessment_results
        self._support_resources = snapshot.support_resources
        self._safety_support_tasks = snapshot.safety_support_tasks
        self._work_tasks = snapshot.work_tasks
        self._extra_collections = snapshot.extra_collections
        self._identity_counter = snapshot.identity_counter
        self._consent_counter = snapshot.consent_counter
        self._anonymous_counter = snapshot.anonymous_counter
        self._assessment_session_counter = snapshot.assessment_session_counter
        self._assessment_result_counter = snapshot.assessment_result_counter
        self._safety_support_task_counter = snapshot.safety_support_task_counter
        self._work_task_counter = snapshot.work_task_counter

    def get_user(self, user_id: str) -> UserAccountDocument:
        with self._lock:
            try:
                return self._users[user_id]
            except KeyError as error:
                raise RepositoryNotFound("user not found") from error

    def save_user(self, user: UserAccountDocument, *, expected_version: int) -> UserAccountDocument:
        with self._lock:
            current = self.get_user(user.document_id)
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

    def append_consent_event(self, consent: ConsentEventDocument) -> ConsentEventDocument:
        with self._lock:
            self._consents[consent.document_id] = consent
            return consent

    def list_consent_events(self, user_id: str) -> tuple[ConsentEventDocument, ...]:
        with self._lock:
            events = [event for event in self._consents.values() if event.user_id == user_id]
            events.sort(key=lambda event: (event.occurred_at, event.document_id))
            return tuple(events)

    def create_identity_record(self, identity: IdentityRecordDocument) -> IdentityRecordDocument:
        with self._lock:
            self._identities[identity.document_id] = identity
            return identity

    def save_identity_record(
        self,
        identity: IdentityRecordDocument,
        *,
        expected_version: int,
    ) -> IdentityRecordDocument:
        with self._lock:
            current = self.get_identity_record(identity.document_id)
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

    def get_identity_record(self, identity_record_id: str) -> IdentityRecordDocument:
        with self._lock:
            try:
                return self._identities[identity_record_id]
            except KeyError as error:
                raise RepositoryNotFound("identity record not found") from error

    def get_identity_record_by_user(self, user_id: str) -> IdentityRecordDocument | None:
        with self._lock:
            for record in self._identities.values():
                if record.user_id == user_id:
                    return record
            return None

    def create_anonymous_identity(
        self,
        anonymous_identity: AnonymousIdentityDocument,
    ) -> AnonymousIdentityDocument:
        with self._lock:
            self._anonymous[anonymous_identity.document_id] = anonymous_identity
            return anonymous_identity

    def get_anonymous_identity(self, anonymous_identity_id: str) -> AnonymousIdentityDocument:
        with self._lock:
            try:
                return self._anonymous[anonymous_identity_id]
            except KeyError as error:
                raise RepositoryNotFound("anonymous identity not found") from error

    def get_active_anonymous_identity_by_user(
        self,
        user_id: str,
    ) -> AnonymousIdentityDocument | None:
        with self._lock:
            for identity in self._anonymous.values():
                if identity.user_id == user_id and identity.status == "active":
                    return identity
            return None

    def list_anonymous_identities(self, user_id: str) -> tuple[AnonymousIdentityDocument, ...]:
        with self._lock:
            identities = [
                identity for identity in self._anonymous.values() if identity.user_id == user_id
            ]
            identities.sort(key=lambda identity: (identity.created_at, identity.document_id))
            return tuple(identities)

    def next_consent_id(self) -> str:
        with self._lock:
            self._consent_counter += 1
            return f"consent_{self._consent_counter:04d}"

    def next_identity_record_id(self) -> str:
        with self._lock:
            self._identity_counter += 1
            return f"identity_{self._identity_counter:04d}"

    def next_anonymous_identity_id(self) -> str:
        with self._lock:
            self._anonymous_counter += 1
            return f"anonymous_{self._anonymous_counter:04d}"

    def get_assessment_module(self, module_code: str) -> AssessmentModuleDocument:
        with self._lock:
            try:
                return self._assessment_modules[module_code]
            except KeyError as error:
                raise RepositoryNotFound("assessment module not found") from error

    def replace_assessment_module(
        self,
        module: AssessmentModuleDocument,
        *,
        expected_version: int,
    ) -> AssessmentModuleDocument:
        with self._lock:
            current = self.get_assessment_module(module.module_code)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = module.model_copy(
                update={"updated_at": datetime.now(UTC), "version": current.version + 1}
            )
            self._assessment_modules[module.module_code] = updated
            return updated

    def get_assessment_questionnaire(
        self,
        module_code: str,
        questionnaire_version: str,
    ) -> AssessmentQuestionnaireDocument:
        with self._lock:
            key = (module_code, questionnaire_version)
            try:
                return self._assessment_questionnaires[key]
            except KeyError as error:
                raise RepositoryNotFound("assessment questionnaire not found") from error

    def create_assessment_session(
        self, session: AssessmentSessionDocument
    ) -> AssessmentSessionDocument:
        with self._lock:
            self._assessment_sessions[session.document_id] = session
            return session

    def get_assessment_session(self, session_id: str) -> AssessmentSessionDocument:
        with self._lock:
            try:
                return self._assessment_sessions[session_id]
            except KeyError as error:
                raise RepositoryNotFound("assessment session not found") from error

    def save_assessment_session(
        self,
        session: AssessmentSessionDocument,
        *,
        expected_version: int,
    ) -> AssessmentSessionDocument:
        with self._lock:
            current = self.get_assessment_session(session.document_id)
            if current.version != expected_version:
                raise RepositoryVersionConflict(current.version)
            updated = session.model_copy(
                update={"updated_at": datetime.now(UTC), "version": current.version + 1}
            )
            self._assessment_sessions[session.document_id] = updated
            return updated

    def create_assessment_result(
        self,
        result: AssessmentResultDocument,
    ) -> AssessmentResultDocument:
        with self._lock:
            if self.get_assessment_result_by_session(result.session_id) is not None:
                raise RepositoryVersionConflict(1)
            self._assessment_results[result.document_id] = result
            return result

    def get_assessment_result(self, result_id: str) -> AssessmentResultDocument:
        with self._lock:
            try:
                return self._assessment_results[result_id]
            except KeyError as error:
                raise RepositoryNotFound("assessment result not found") from error

    def get_assessment_result_by_session(
        self,
        session_id: str,
    ) -> AssessmentResultDocument | None:
        with self._lock:
            for result in self._assessment_results.values():
                if result.session_id == session_id:
                    return result
            return None

    def list_assessment_results_by_session(
        self,
        session_id: str,
    ) -> tuple[AssessmentResultDocument, ...]:
        with self._lock:
            results = [
                result
                for result in self._assessment_results.values()
                if result.session_id == session_id
            ]
            results.sort(key=lambda result: (result.created_at, result.document_id))
            return tuple(results)

    def list_support_resources(self, environment_scope: str) -> tuple[SupportResourceDocument, ...]:
        with self._lock:
            resources = [
                resource
                for resource in self._support_resources.values()
                if resource.environment_scope == environment_scope and resource.enabled
            ]
            resources.sort(key=lambda resource: (resource.sort_order, resource.document_id))
            return tuple(resources)

    def create_safety_support_task(
        self,
        task: SafetySupportTaskDocument,
    ) -> SafetySupportTaskDocument:
        with self._lock:
            self._safety_support_tasks[task.document_id] = task
            return task

    def list_safety_support_tasks(self) -> tuple[SafetySupportTaskDocument, ...]:
        with self._lock:
            tasks = list(self._safety_support_tasks.values())
            tasks.sort(key=lambda task: (task.created_at, task.document_id))
            return tuple(tasks)

    def create_work_task(self, task: WorkTaskDocument) -> WorkTaskDocument:
        with self._lock:
            self._work_tasks[task.document_id] = task
            return task

    def next_assessment_session_id(self) -> str:
        with self._lock:
            self._assessment_session_counter += 1
            return f"assessment_session_{self._assessment_session_counter:04d}"

    def next_assessment_result_id(self) -> str:
        with self._lock:
            self._assessment_result_counter += 1
            return f"assessment_result_{self._assessment_result_counter:04d}"

    def next_safety_support_task_id(self) -> str:
        with self._lock:
            self._safety_support_task_counter += 1
            return f"safety_support_task_{self._safety_support_task_counter:04d}"

    def next_work_task_id(self) -> str:
        with self._lock:
            self._work_task_counter += 1
            return f"work_task_{self._work_task_counter:04d}"

    def extra_collection(self, name: str) -> list[dict[str, Any]]:
        with self._lock:
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
            if name == "support_resources":
                return [
                    resource.model_dump(by_alias=True, mode="json")
                    for resource in sorted(
                        self._support_resources.values(),
                        key=lambda resource: (resource.sort_order, resource.document_id),
                    )
                ]
            return deepcopy(self._extra_collections.get(name, []))
