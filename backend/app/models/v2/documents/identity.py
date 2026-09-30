from __future__ import annotations

from datetime import datetime
from typing import Literal

from .common import (
    DocumentModel,
    NonEmptyString,
    VersionInt,
)


class IdentityRecordDocument(DocumentModel):
    user_id: NonEmptyString
    verification_status: Literal["not_started", "pending", "verified", "failed", "unavailable"]
    student_name_ciphertext: str | None = None
    student_number_ciphertext: str | None = None
    provider_reference_hash: str | None = None
    verified_at: datetime | None = None
    failed_reason_code: str | None = None
    access_version: VersionInt


class AnonymousIdentityDocument(DocumentModel):
    user_id: NonEmptyString
    display_name: NonEmptyString
    generation_version: NonEmptyString
    status: Literal["active", "retired"]


class IdentityAccessRequestDocument(DocumentModel):
    task_kind: Literal["identity_access"]
    user_reference_id: NonEmptyString
    requester_admin_id: NonEmptyString
    requested_fields: list[Literal["student_name", "student_number"]]
    reason_fact: NonEmptyString
    state: Literal["pending", "approved", "denied", "expired", "revoked"]
    decided_admin_id: str | None = None
    decision_reason: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
