"""Identity verification and anonymous identity orchestration."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.domain.models import AnonymousIdentityDocument, IdentityRecordDocument, UserAccountDocument
from app.integrations.school_identity import (
    HttpSchoolIdentityProvider,
    SchoolIdentityProvider,
    SchoolIdentityVerificationResult,
    UnavailableSchoolIdentityProvider,
)
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.protocols import (
    RepositoryError,
    RepositoryNotFound,
    RepositoryVersionConflict,
)
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager
from app.services.idempotency_service import (
    IdempotencyReservation,
    IdempotencyService,
    deserialize_api_error,
    serialize_api_error,
)

logger = logging.getLogger(__name__)

IdentityVerificationStatus = Literal["not_started", "pending", "verified", "failed", "unavailable"]
StudentSessionIdentityStatus = Literal["unverified", "pending", "verified"]


class IdentityCipher(Protocol):
    def encrypt(self, value: str) -> str: ...


@dataclass(frozen=True, slots=True)
class IdentityVerificationState:
    verification_status: IdentityVerificationStatus
    identity_record_id: str
    anonymous_identity_id: str | None


class HmacIdentityCipher:
    """Small local authenticated-encryption boundary for identity fields.

    The application keeps the key outside the document store. A random nonce,
    HMAC-derived keystream, and authentication tag keep plaintext out of the
    stored value while avoiding a dependency on a crypto package in this phase.
    Production deployments should replace this boundary with managed AEAD.
    """

    NONCE_SIZE = 16
    TAG_SIZE = hashlib.sha256().digest_size

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("identity cipher secret cannot be empty")
        secret_bytes = secret.encode("utf-8")
        self._encryption_key = hmac.new(
            secret_bytes,
            b"xinyu/identity/encryption/v1",
            hashlib.sha256,
        ).digest()
        self._authentication_key = hmac.new(
            secret_bytes,
            b"xinyu/identity/authentication/v1",
            hashlib.sha256,
        ).digest()

    def encrypt(self, value: str) -> str:
        nonce = secrets.token_bytes(self.NONCE_SIZE)
        plaintext = value.encode("utf-8")
        keystream = _hmac_keystream(self._encryption_key, nonce, len(plaintext))
        ciphertext = bytes(left ^ right for left, right in zip(plaintext, keystream))
        tag = hmac.new(
            self._authentication_key,
            nonce + ciphertext,
            hashlib.sha256,
        ).digest()
        encoded = _urlsafe_encode(nonce + ciphertext + tag)
        return f"enc:v1:{encoded}"


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
        self._identity_secret = settings.session_secret or secrets.token_urlsafe(32)
        self.identity_cipher = identity_cipher or HmacIdentityCipher(self._identity_secret)

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
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        if not isinstance(student_name, str) or not student_name.strip():
            raise ApiException(422, "VALIDATION_FAILED")
        if not isinstance(student_number, str) or not student_number.strip():
            raise ApiException(422, "VALIDATION_FAILED")
        student_name = student_name.strip()
        student_number = student_number.strip()
        reservation = self.idempotency.begin(
            "student",
            subject.subject_id,
            "/identity/verify",
            idempotency_key,
            _identity_request_fingerprint(
                self._identity_secret,
                student_name=student_name,
                student_number=student_number,
                user_version=user_version,
            ),
        )
        if reservation.replayed:
            return _verification_state_from_digest(reservation.record.response_digest)

        try:
            user = self.repository.get_user(subject.subject_id)
            if user.status != "active":
                raise ApiException(403, "FORBIDDEN")
            if user.base_consent_status != "accepted":
                raise ApiException(403, "CONSENT_REQUIRED")
            if user.version != user_version:
                raise ApiException(409, "VERSION_CONFLICT", current_version=user.version)

            existing_record = _get_bound_identity_record(self.repository, user)
            if user.identity_record_id is not None and existing_record is None:
                raise ApiException(409, "VERSION_CONFLICT", current_version=user.version)
            if existing_record is not None and existing_record.verification_status in {
                "pending",
                "verified",
            }:
                raise ApiException(409, "VERSION_CONFLICT", current_version=user.version)

            result = await _verify_school_identity(
                self.school,
                student_name=student_name,
                student_number=student_number,
            )
            current = datetime.now(UTC)
            with self.repository.transaction():
                current_user = self.repository.get_user(subject.subject_id)
                if current_user.status != "active":
                    raise ApiException(403, "FORBIDDEN")
                if current_user.base_consent_status != "accepted":
                    raise ApiException(403, "CONSENT_REQUIRED")
                if current_user.version != user_version:
                    raise ApiException(
                        409,
                        "VERSION_CONFLICT",
                        current_version=current_user.version,
                    )
                if current_user.identity_record_id != user.identity_record_id:
                    raise ApiException(
                        409,
                        "VERSION_CONFLICT",
                        current_version=current_user.version,
                    )

                current_record = _get_bound_identity_record(self.repository, current_user)
                if current_user.identity_record_id is not None and current_record is None:
                    raise ApiException(
                        409,
                        "VERSION_CONFLICT",
                        current_version=current_user.version,
                    )
                if existing_record is None:
                    if current_record is not None:
                        raise ApiException(
                            409,
                            "VERSION_CONFLICT",
                            current_version=current_user.version,
                        )
                elif (
                    current_record is None
                    or current_record.document_id != existing_record.document_id
                    or current_record.version != existing_record.version
                ):
                    raise ApiException(
                        409,
                        "VERSION_CONFLICT",
                        current_version=current_user.version,
                    )
                if current_record is not None and current_record.verification_status in {
                    "pending",
                    "verified",
                }:
                    raise ApiException(
                        409,
                        "VERSION_CONFLICT",
                        current_version=current_user.version,
                    )

                identity_record = _build_identity_record(
                    repository=self.repository,
                    user_id=current_user.document_id,
                    verification=result,
                    occurred_at=current,
                    cipher=self.identity_cipher,
                    student_name=student_name,
                    student_number=student_number,
                    existing_record=current_record,
                )
                if current_record is None:
                    saved_identity = self.repository.create_identity_record(identity_record)
                else:
                    saved_identity = self.repository.save_identity_record(
                        identity_record,
                        expected_version=current_record.version,
                    )

                anonymous_id = current_user.anonymous_identity_id
                if result.status == "verified" and anonymous_id is None:
                    anonymous = AnonymousIdentityDocument(
                        _id=self.repository.next_anonymous_identity_id(),
                        user_id=current_user.document_id,
                        display_name=_generate_display_name(current_user.document_id),
                        generation_version=self.ANONYMOUS_GENERATION_VERSION,
                        status="active",
                        created_at=current,
                        updated_at=current,
                        version=1,
                    )
                    self.repository.create_anonymous_identity(anonymous)
                    anonymous_id = anonymous.document_id
                saved_user = self.repository.save_user(
                    current_user.model_copy(
                        update={
                            "identity_record_id": saved_identity.document_id,
                            "anonymous_identity_id": anonymous_id,
                        }
                    ),
                    expected_version=current_user.version,
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
        except RepositoryVersionConflict as error:
            conflict = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            _complete_failure(self.idempotency, reservation, conflict)
            raise conflict from error
        except RepositoryError as error:
            failure = _repository_failure(error)
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except ApiException as error:
            _complete_failure(self.idempotency, reservation, error)
            raise
        except Exception as error:
            failure = ApiException(500, "INTERNAL_ERROR")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error

        try:
            self.audit.write(
                request_id=request_id,
                actor_type="student",
                actor_id=subject.subject_id,
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
        except Exception:
            logger.warning("audit_write_failed")
        return state

    def get_identity_status(self, access_token: str) -> dict[str, str]:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        user = self.repository.get_user(subject.subject_id)
        record = _get_bound_identity_record(self.repository, user)
        verification_status: IdentityVerificationStatus = (
            record.verification_status if record is not None else "not_started"
        )
        return {
            "verification_status": verification_status,
            "identity_status": to_student_session_identity_status(verification_status),
        }

    def get_verification(
        self, access_token: str, verification_id: str
    ) -> dict[str, str | int | None]:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        user = self.repository.get_user(subject.subject_id)
        record = _get_bound_identity_record(self.repository, user)
        if record is None or record.document_id != verification_id:
            raise ApiException(404, "NOT_FOUND")
        return {
            "verification_id": record.document_id,
            "status": record.verification_status,
            "next_poll_after_seconds": 5 if record.verification_status == "pending" else None,
        }

    def get_anonymous_identity(self, access_token: str) -> dict[str, str]:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        user = self.repository.get_user(subject.subject_id)
        if not user.anonymous_identity_id:
            raise ApiException(404, "NOT_FOUND")
        try:
            anonymous = self.repository.get_anonymous_identity(user.anonymous_identity_id)
        except RepositoryNotFound as error:
            raise ApiException(404, "NOT_FOUND") from error
        if anonymous.user_id != user.document_id:
            raise ApiException(404, "NOT_FOUND")
        return {
            "anonymous_identity_id": anonymous.document_id,
            "display_name": anonymous.display_name,
            "display_scope": "treehole_only",
            "generation_version": anonymous.generation_version,
            "status": anonymous.status,
        }

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
    failed_reason_code = _safe_failed_reason_code(verification)
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
            failed_reason_code=failed_reason_code,
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
            "failed_reason_code": failed_reason_code,
        }
    )


def _hash_reference(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def to_student_session_identity_status(
    verification_status: IdentityVerificationStatus,
) -> StudentSessionIdentityStatus:
    if verification_status == "pending":
        return "pending"
    if verification_status == "verified":
        return "verified"
    return "unverified"


SAFE_FAILED_REASON_CODES = frozenset({"mismatch", "invalid_request", "provider_rejected"})


def _safe_failed_reason_code(verification: SchoolIdentityVerificationResult) -> str | None:
    if verification.status != "failed" or not verification.failed_reason_code:
        return None
    if verification.failed_reason_code in SAFE_FAILED_REASON_CODES:
        return verification.failed_reason_code
    return "provider_rejected"


def _identity_request_fingerprint(
    secret: str,
    *,
    student_name: str,
    student_number: str,
    user_version: int,
) -> dict[str, object]:
    return {
        "student_name_digest": _keyed_digest(secret, "student_name", student_name),
        "student_number_digest": _keyed_digest(secret, "student_number", student_number),
        "user_version": user_version,
    }


def _keyed_digest(secret: str, field_name: str, value: str) -> str:
    message = f"{field_name}\x00{value}".encode()
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _complete_failure(
    idempotency: IdempotencyService,
    reservation: IdempotencyReservation,
    error: ApiException,
) -> None:
    idempotency.complete(
        reservation,
        status_code=error.status_code,
        response_digest=serialize_api_error(error),
        outcome="failure",
    )


def _get_bound_identity_record(
    repository: InMemoryDomainDataRepository,
    user: UserAccountDocument,
) -> IdentityRecordDocument | None:
    if not user.identity_record_id:
        return None
    try:
        record = repository.get_identity_record(user.identity_record_id)
    except RepositoryNotFound:
        return None
    if record.user_id != user.document_id:
        return None
    return record


async def _verify_school_identity(
    school: SchoolIdentityProvider,
    *,
    student_name: str,
    student_number: str,
) -> SchoolIdentityVerificationResult:
    try:
        result = await school.verify_student(
            student_name=student_name,
            student_number=student_number,
        )
    except Exception:
        return SchoolIdentityVerificationResult(status="unavailable")
    if not isinstance(result, SchoolIdentityVerificationResult):
        return SchoolIdentityVerificationResult(status="unavailable")
    if result.status == "verified" and not result.provider_reference:
        return SchoolIdentityVerificationResult(status="unavailable")
    return result


def _repository_failure(error: RepositoryError) -> ApiException:
    if isinstance(error, RepositoryNotFound):
        return ApiException(404, "NOT_FOUND")
    return ApiException(503, "DEPENDENCY_UNAVAILABLE")


def _hmac_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    blocks = [
        hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        for counter in range((length + 31) // 32)
    ]
    return b"".join(blocks)[:length]


def _urlsafe_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _generate_display_name(user_id: str) -> str:
    digest = hashlib.sha256(f"anonymous:{user_id}".encode()).hexdigest()[:6].upper()
    return f"树洞同学{digest}"


def _verification_state_from_digest(response_digest: str | None) -> IdentityVerificationState:
    if response_digest is None:
        raise ApiException(500, "INTERNAL_ERROR")
    try:
        error = deserialize_api_error(response_digest)
        if error is not None:
            raise error
        data = json.loads(response_digest)
        return IdentityVerificationState(**data)
    except ApiException:
        raise
    except (TypeError, ValueError, KeyError) as error:
        raise ApiException(500, "INTERNAL_ERROR") from error
