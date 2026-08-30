"""Minimal typed repository for consent and identity domain data."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.domain.models import (
    AnonymousIdentityDocument,
    ConsentEventDocument,
    IdentityRecordDocument,
    UserAccountDocument,
)
from app.repositories.protocols import RepositoryNotFound, RepositoryVersionConflict


class InMemoryDomainDataRepository:
    def __init__(
        self,
        *,
        users: list[UserAccountDocument] | None = None,
        consents: list[ConsentEventDocument] | None = None,
        identities: list[IdentityRecordDocument] | None = None,
        anonymous_identities: list[AnonymousIdentityDocument] | None = None,
        extra_collections: Mapping[str, list[Mapping[str, Any]]] | None = None,
    ) -> None:
        self._users = {user.document_id: user for user in users or []}
        self._consents = {consent.document_id: consent for consent in consents or []}
        self._identities = {identity.document_id: identity for identity in identities or []}
        self._anonymous = {
            anonymous_identity.document_id: anonymous_identity
            for anonymous_identity in anonymous_identities or []
        }
        self._extra_collections = {
            name: [deepcopy(dict(item)) for item in items]
            for name, items in (extra_collections or {}).items()
        }
        self._identity_counter = len(self._identities)
        self._consent_counter = len(self._consents)
        self._anonymous_counter = len(self._anonymous)

    def get_user(self, user_id: str) -> UserAccountDocument:
        try:
            return self._users[user_id]
        except KeyError as error:
            raise RepositoryNotFound("user not found") from error

    def save_user(self, user: UserAccountDocument, *, expected_version: int) -> UserAccountDocument:
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
        self._consents[consent.document_id] = consent
        return consent

    def list_consent_events(self, user_id: str) -> tuple[ConsentEventDocument, ...]:
        events = [event for event in self._consents.values() if event.user_id == user_id]
        events.sort(key=lambda event: (event.occurred_at, event.document_id))
        return tuple(events)

    def create_identity_record(self, identity: IdentityRecordDocument) -> IdentityRecordDocument:
        self._identities[identity.document_id] = identity
        return identity

    def save_identity_record(
        self,
        identity: IdentityRecordDocument,
        *,
        expected_version: int,
    ) -> IdentityRecordDocument:
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
        try:
            return self._identities[identity_record_id]
        except KeyError as error:
            raise RepositoryNotFound("identity record not found") from error

    def get_identity_record_by_user(self, user_id: str) -> IdentityRecordDocument | None:
        for record in self._identities.values():
            if record.user_id == user_id:
                return record
        return None

    def create_anonymous_identity(
        self,
        anonymous_identity: AnonymousIdentityDocument,
    ) -> AnonymousIdentityDocument:
        self._anonymous[anonymous_identity.document_id] = anonymous_identity
        return anonymous_identity

    def get_anonymous_identity(self, anonymous_identity_id: str) -> AnonymousIdentityDocument:
        try:
            return self._anonymous[anonymous_identity_id]
        except KeyError as error:
            raise RepositoryNotFound("anonymous identity not found") from error

    def get_active_anonymous_identity_by_user(
        self,
        user_id: str,
    ) -> AnonymousIdentityDocument | None:
        for identity in self._anonymous.values():
            if identity.user_id == user_id and identity.status == "active":
                return identity
        return None

    def list_anonymous_identities(self, user_id: str) -> tuple[AnonymousIdentityDocument, ...]:
        identities = [
            identity for identity in self._anonymous.values() if identity.user_id == user_id
        ]
        identities.sort(key=lambda identity: (identity.created_at, identity.document_id))
        return tuple(identities)

    def next_consent_id(self) -> str:
        self._consent_counter += 1
        return f"consent_{self._consent_counter:04d}"

    def next_identity_record_id(self) -> str:
        self._identity_counter += 1
        return f"identity_{self._identity_counter:04d}"

    def next_anonymous_identity_id(self) -> str:
        self._anonymous_counter += 1
        return f"anonymous_{self._anonymous_counter:04d}"

    def extra_collection(self, name: str) -> list[dict[str, Any]]:
        return deepcopy(self._extra_collections.get(name, []))
