from __future__ import annotations

from datetime import datetime
from typing import Literal

from .common import (
    DocumentModel,
    NonEmptyString,
)


class UserAccountDocument(DocumentModel):
    auth_subject_hash: NonEmptyString
    status: Literal["active", "recovery_pending", "stopped", "purged"]
    base_consent_status: Literal["accepted", "not_accepted"]
    base_consent_version: str | None = None
    base_consent_at: datetime | None = None
    community_consent_status: Literal["accepted", "withdrawn", "not_accepted"]
    community_consent_version: str | None = None
    community_consent_at: datetime | None = None
    identity_record_id: str | None = None
    anonymous_identity_id: str | None = None
    stop_requested_at: datetime | None = None
    recovery_deadline_at: datetime | None = None
    purged_at: datetime | None = None


class AuthSessionDocument(DocumentModel):
    subject_type: Literal["student", "admin"]
    subject_id: NonEmptyString
    access_token_hash: NonEmptyString
    refresh_token_hash: str | None = None
    status: Literal["active", "revoked", "expired"]
    access_expires_at: datetime
    refresh_expires_at: datetime | None = None
    last_seen_at: datetime
    device_hash: str | None = None
    credential_version: str | None = None


class AdminAccountDocument(DocumentModel):
    login_name: NonEmptyString
    display_name: NonEmptyString
    capability_label: NonEmptyString
    status: Literal["active", "disabled"]
    password_hash_reference: NonEmptyString
    last_login_at: datetime | None = None
