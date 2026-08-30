"""Identity verification and anonymous identity orchestration."""

from __future__ import annotations

import base64
import hashlib
import itertools
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.domain.models import AnonymousIdentityDocument, IdentityRecordDocument
from app.integrations.school_identity import (
    HttpSchoolIdentityProvider,
    SchoolIdentityProvider,
    SchoolIdentityVerificationResult,
    UnavailableSchoolIdentityProvider,
)
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager
from app.services.idempotency_service import IdempotencyService


class IdentityCipher(Protocol):
    def encrypt(self, value: str) -> str: ...


@dataclass(frozen=True, slots=True)
class IdentityVerificationState:
    verification_status: str
    identity_record_id: str
    anonymous_identity_id: str | None


class XorIdentityCipher:
    def __init__(self, secret: str) -> None:
        secret_bytes = secret.encode("utf-8")
        self._key = secret_bytes or b"xinyu-default"

    def encrypt(self, value: str) -> str:
        encoded = value.encode("utf-8")
        xored = bytes(
            byte ^ key_byte for byte, key_byte in zip(encoded, itertools.cycle(self._key))
        )
        return "enc::" + base64.urlsafe_b64encode(xored).decode("ascii")


class IdentityService:
    ANONYMOUS_GENERATION_VERSION = "anon-v1"

    def __init__(
        self,
        *,
        settings: Settings,
        repository: InMemoryDomainDataRepository,
        session_repository: InMemorySessionRepository,
        token_manager: TokenManager,
        school_identity_provider: SchoolIdentityProvider | None = None,
        idempotency_service: IdempotencyService,
        audit_writer: AuditWriter,
        identity_cipher: IdentityCipher | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.sessions = session_repository
        self.tokens = token_manager
        self.school = school_identity_provider or self._default_school_provider()
        self.idempotency = idempotency_service
        self.audit = audit_writer
        self.identity_cipher = identity_cipher or XorIdentityCipher(
            settings.session_secret or "identity-secret"
        )

    async def verify_student_identity(
        self,
        access_token: str,
        *,
        student_name: str,
        student_number: str,
        user_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> IdentityVerificationState:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        reservation = self.idempotency.begin(
            "student",
            subject.subject_id,
            "/identity/verify",
            idempotency_key,
            {
                "student_name": "***",
                "student_number": "***",
                "user_version": user_version,
            },
        )
        if reservation.replayed:
            return _verification_state_from_digest(reservation.record.response_digest)

        user = self.repository.get_user(subject.subject_id)
        if user.version != user_version:
            raise ApiException(409, "VERSION_CONFLICT", current_version=user.version)
        result = await self.school.verify_student(
            student_name=student_name,
            student_number=student_number,
        )
        current = datetime.now(UTC)
        existing_record = self.repository.get_identity_record_by_user(user.document_id)
        identity_record = _build_identity_record(
            repository=self.repository,
            user_id=user.document_id,
            verification=result,
            occurred_at=current,
            cipher=self.identity_cipher,
            student_name=student_name,
            student_number=student_number,
            existing_record=existing_record,
        )
        if existing_record is None:
            saved_identity = self.repository.create_identity_record(identity_record)
        else:
            saved_identity = self.repository.save_identity_record(
                identity_record,
                expected_version=existing_record.version,
            )

        anonymous_id = user.anonymous_identity_id
        if result.status == "verified" and user.anonymous_identity_id is None:
            anonymous = AnonymousIdentityDocument(
                _id=self.repository.next_anonymous_identity_id(),
                user_id=user.document_id,
                display_name=_generate_display_name(user.document_id),
                generation_version=self.ANONYMOUS_GENERATION_VERSION,
                status="active",
                created_at=current,
                updated_at=current,
                version=1,
            )
            self.repository.create_anonymous_identity(anonymous)
            anonymous_id = anonymous.document_id
        saved_user = self.repository.save_user(
            user.model_copy(
                update={
                    "identity_record_id": saved_identity.document_id,
                    "anonymous_identity_id": anonymous_id,
                }
            ),
            expected_version=user_version,
        )
        state = IdentityVerificationState(
            verification_status=saved_identity.verification_status,
            identity_record_id=saved_identity.document_id,
            anonymous_identity_id=saved_user.anonymous_identity_id,
        )
        response_digest = json.dumps(
            asdict(state),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        self.idempotency.complete(reservation, status_code=200, response_digest=response_digest)
        self.audit.write(
            request_id=request_id,
            actor_type="student",
            actor_id=user.document_id,
            capability=None,
            action="identity_verification",
            resource_type="identity",
            resource_id=saved_identity.document_id,
            data_scope="necessary_facts",
            outcome="success",
            reason_code=result.status,
            occurred_at=current,
            facts={
                "action_code": "verify",
                "object_version": saved_identity.version,
                "status": saved_identity.verification_status,
            },
        )
        return state

    def get_identity_status(self, access_token: str) -> dict[str, str]:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        user = self.repository.get_user(subject.subject_id)
        record = self._require_identity_record(user.identity_record_id)
        return {"verification_status": record.verification_status}

    def get_anonymous_identity(self, access_token: str) -> dict[str, str]:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        user = self.repository.get_user(subject.subject_id)
        if not user.anonymous_identity_id:
            raise ApiException(404, "NOT_FOUND")
        anonymous = self.repository.get_anonymous_identity(user.anonymous_identity_id)
        return {
            "anonymous_identity_id": anonymous.document_id,
            "display_name": anonymous.display_name,
        }

    def _require_identity_record(self, identity_record_id: str | None) -> IdentityRecordDocument:
        if not identity_record_id:
            raise ApiException(404, "NOT_FOUND")
        return self.repository.get_identity_record(identity_record_id)

    def _default_school_provider(self) -> SchoolIdentityProvider:
        if not self.settings.school_identity_provider_url:
            return UnavailableSchoolIdentityProvider()
        return HttpSchoolIdentityProvider(
            provider_url=self.settings.school_identity_provider_url,
        )


def _build_identity_record(
    *,
    repository: InMemoryDomainDataRepository,
    user_id: str,
    verification: SchoolIdentityVerificationResult,
    occurred_at: datetime,
    cipher: IdentityCipher,
    student_name: str,
    student_number: str,
    existing_record: IdentityRecordDocument | None,
) -> IdentityRecordDocument:
    if existing_record is None:
        return IdentityRecordDocument(
            _id=repository.next_identity_record_id(),
            user_id=user_id,
            verification_status=verification.status,
            student_name_ciphertext=(
                cipher.encrypt(student_name) if verification.status == "verified" else None
            ),
            student_number_ciphertext=(
                cipher.encrypt(student_number) if verification.status == "verified" else None
            ),
            provider_reference_hash=_hash_reference(verification.provider_reference),
            verified_at=occurred_at if verification.status == "verified" else None,
            failed_reason_code=verification.failed_reason_code,
            access_version=1,
            created_at=occurred_at,
            updated_at=occurred_at,
            version=1,
        )
    return existing_record.model_copy(
        update={
            "verification_status": verification.status,
            "student_name_ciphertext": (
                cipher.encrypt(student_name) if verification.status == "verified" else None
            ),
            "student_number_ciphertext": (
                cipher.encrypt(student_number) if verification.status == "verified" else None
            ),
            "provider_reference_hash": _hash_reference(verification.provider_reference),
            "verified_at": occurred_at if verification.status == "verified" else None,
            "failed_reason_code": verification.failed_reason_code,
        }
    )


def _hash_reference(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _generate_display_name(user_id: str) -> str:
    digest = hashlib.sha256(f"anonymous:{user_id}".encode()).hexdigest()[:6].upper()
    return f"树洞同学{digest}"


def _verification_state_from_digest(response_digest: str | None) -> IdentityVerificationState:
    if response_digest is None:
        raise ApiException(500, "INTERNAL_ERROR")
    data = json.loads(response_digest)
    return IdentityVerificationState(**data)
