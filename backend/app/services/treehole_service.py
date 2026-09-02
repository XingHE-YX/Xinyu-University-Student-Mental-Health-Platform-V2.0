from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.domain.models import TreeholePostDocument, TreeholeResponseDocument
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.protocols import (
    RepositoryError,
    RepositoryNotFound,
    RepositoryVersionConflict,
)
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.schemas.treehole import (
    TreeholeDeleteResponse,
    TreeholeMutationResponse,
    TreeholePostListResponse,
    TreeholePostProjection,
    TreeholeResponseProjection,
)
from app.security.tokens import AuthenticatedSubject, TokenManager
from app.services.consent_service import ConsentService
from app.services.idempotency_service import (
    IdempotencyReservation,
    IdempotencyService,
    deserialize_api_error,
    serialize_api_error,
)


class TreeholeService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: InMemoryDomainDataRepository,
        session_repository: InMemorySessionRepository,
        token_manager: TokenManager,
        idempotency_service: IdempotencyService,
        audit_writer: AuditWriter,
        consent_service: ConsentService,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.sessions = session_repository
        self.tokens = token_manager
        self.idempotency = idempotency_service
        self.audit = audit_writer
        self.consent = consent_service

    def list_public(
        self,
        access_token: str,
        *,
        sort: str = "latest",
        cursor: str | None = None,
        limit: int = 20,
    ) -> TreeholePostListResponse:
        subject = self._student(access_token)
        if sort not in {"latest", "confirmed"} or limit < 1:
            raise ApiException(422, "VALIDATION_FAILED")
        posts = [
            post
            for post in self.repository.list_treehole_posts()
            if post.visibility_state in {"published", "protected"} and post.deleted_at is None
        ]
        if sort == "confirmed":
            posts.sort(
                key=lambda post: (post.visibility_state == "protected", post.created_at),
                reverse=True,
            )
        offset = _decode_cursor(cursor)
        page_size = min(limit, 100)
        page = posts[offset : offset + page_size]
        next_cursor = str(offset + page_size) if offset + page_size < len(posts) else None
        return TreeholePostListResponse(
            items=[
                self._post_projection(post, viewer_id=subject.subject_id, public=True)
                for post in page
            ],
            next_cursor=next_cursor,
        )

    def get_post(self, access_token: str, *, post_id: str) -> TreeholePostProjection:
        subject = self._student(access_token)
        try:
            post = self.repository.get_treehole_post(post_id)
        except RepositoryNotFound as error:
            raise ApiException(404, "NOT_FOUND") from error
        mine = post.author_user_id == subject.subject_id
        if not mine and post.visibility_state not in {"published", "protected"}:
            raise ApiException(404, "NOT_FOUND")
        return self._post_projection(post, viewer_id=subject.subject_id, public=not mine)

    def list_mine(
        self,
        access_token: str,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> TreeholePostListResponse:
        subject = self._student(access_token)
        if limit < 1:
            raise ApiException(422, "VALIDATION_FAILED")
        posts = [
            post
            for post in self.repository.list_treehole_posts()
            if post.author_user_id == subject.subject_id
        ]
        offset = _decode_cursor(cursor)
        page_size = min(limit, 100)
        page = posts[offset : offset + page_size]
        next_cursor = str(offset + page_size) if offset + page_size < len(posts) else None
        return TreeholePostListResponse(
            items=[
                self._post_projection(post, viewer_id=subject.subject_id, public=False)
                for post in page
            ],
            next_cursor=next_cursor,
        )

    def create_post(
        self,
        access_token: str,
        *,
        body: str,
        request_id: str,
        idempotency_key: str,
    ) -> TreeholeMutationResponse:
        if not body.strip():
            raise ApiException(422, "VALIDATION_FAILED")
        subject = self._student(access_token)
        self.consent.ensure_community_write_allowed(access_token)
        reservation = self.idempotency.begin(
            "student", subject.subject_id, "/treehole/posts", idempotency_key, {"body": body}
        )
        if reservation.replayed:
            return _decode_mutation(reservation.record.response_digest)
        try:
            user = self.repository.get_user(subject.subject_id)
            if not user.anonymous_identity_id:
                raise ApiException(403, "IDENTITY_REQUIRED")
            anonymous = self.repository.get_anonymous_identity(user.anonymous_identity_id)
            if anonymous.user_id != user.document_id or anonymous.status != "active":
                raise ApiException(403, "IDENTITY_REQUIRED")
            now = datetime.now(UTC)
            safety = _contains_safety_signal(body)
            state: Literal[
                "checking",
                "published",
                "protected",
                "pending_confirmation",
                "unpublished",
                "safety_priority",
                "deleted",
            ] = "safety_priority" if safety else "checking"
            review_state: Literal[
                "not_started", "automated_checked", "human_required", "decided"
            ] = "human_required"
            post = TreeholePostDocument(
                _id=self.repository.next_treehole_post_id(),
                author_user_id=user.document_id,
                anonymous_identity_id=anonymous.document_id,
                display_name_snapshot=anonymous.display_name,
                body_original_ciphertext=_protected_body(body),
                body_sanitized=None,
                body_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
                visibility_state=state,
                review_state=review_state,
                safety_state="needs_support_review" if safety else "not_triggered",
                community_consent_version=user.community_consent_version or "unknown",
                original_retention_deadline=None,
                deleted_at=None,
                created_at=now,
                updated_at=now,
                version=1,
            )
            with self.repository.transaction():
                saved = self.repository.create_treehole_post(post)
                self.repository.append_extra_document(
                    "content_review_tasks",
                    {
                        "_id": f"content_review_{saved.document_id}",
                        "post_id": saved.document_id,
                        "state": "needs_action",
                        "safety_priority": safety,
                    },
                )
            response = self._mutation(saved, subject.subject_id)
            self.idempotency.complete(
                reservation, status_code=200, response_digest=response.model_dump_json()
            )
            self._audit(
                request_id, subject.subject_id, "treehole_post_create", saved.document_id, state
            )
            return response
        except RepositoryVersionConflict as error:
            failure = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except RepositoryError as error:
            failure = ApiException(503, "DEPENDENCY_UNAVAILABLE")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except ApiException as error:
            _complete_failure(self.idempotency, reservation, error)
            raise
        except Exception as error:
            failure = ApiException(500, "INTERNAL_ERROR")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error

    def withdraw_post(
        self,
        access_token: str,
        *,
        post_id: str,
        object_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> TreeholeMutationResponse:
        return self._change_post_state(
            access_token,
            post_id=post_id,
            object_version=object_version,
            target="unpublished",
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    def delete_post(
        self,
        access_token: str,
        *,
        post_id: str,
        object_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> TreeholeDeleteResponse:
        subject = self._student(access_token)
        reservation = self.idempotency.begin(
            "student",
            subject.subject_id,
            f"/treehole/posts/{post_id}/delete",
            idempotency_key,
            {"post_id": post_id, "object_version": object_version},
        )
        if reservation.replayed:
            return _decode_delete(reservation.record.response_digest)
        try:
            with self.repository.transaction():
                post = self.repository.get_treehole_post(post_id)
                self._check_owner(post.author_user_id, subject.subject_id)
                if post.version != object_version:
                    raise ApiException(409, "VERSION_CONFLICT", current_version=post.version)
                if post.deleted_at is not None:
                    raise ApiException(404, "NOT_FOUND")
                now = datetime.now(UTC)
                saved = self.repository.save_treehole_post(
                    post.model_copy(
                        update={
                            "visibility_state": "deleted",
                            "deleted_at": now,
                            "body_sanitized": None,
                        }
                    ),
                    expected_version=post.version,
                )
                response = TreeholeDeleteResponse(
                    resource_id=saved.document_id,
                    deleted_at=saved.deleted_at or now,
                    object_version=saved.version,
                )
            self.idempotency.complete(
                reservation, status_code=200, response_digest=response.model_dump_json()
            )
            self._audit(request_id, subject.subject_id, "treehole_post_delete", post_id, "deleted")
            return response
        except RepositoryNotFound as error:
            failure = ApiException(404, "NOT_FOUND")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except RepositoryVersionConflict as error:
            failure = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except ApiException as error:
            _complete_failure(self.idempotency, reservation, error)
            raise
        except Exception as error:
            failure = ApiException(500, "INTERNAL_ERROR")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error

    def create_response(
        self,
        access_token: str,
        *,
        post_id: str,
        body: str,
        object_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> TreeholeResponseProjection:
        subject = self._student(access_token)
        self.consent.ensure_community_write_allowed(access_token)
        reservation = self.idempotency.begin(
            "student",
            subject.subject_id,
            f"/treehole/posts/{post_id}/responses",
            idempotency_key,
            {"post_id": post_id, "body": body, "object_version": object_version},
        )
        if reservation.replayed:
            return _decode_response(reservation.record.response_digest)
        try:
            post = self.repository.get_treehole_post(post_id)
            if (
                post.visibility_state not in {"published", "protected"}
                or post.deleted_at is not None
            ):
                raise ApiException(404, "NOT_FOUND")
            if post.version != object_version:
                raise ApiException(409, "VERSION_CONFLICT", current_version=post.version)
            user = self.repository.get_user(subject.subject_id)
            if not user.anonymous_identity_id:
                raise ApiException(403, "IDENTITY_REQUIRED")
            anonymous = self.repository.get_anonymous_identity(user.anonymous_identity_id)
            now = datetime.now(UTC)
            response = TreeholeResponseDocument(
                _id=self.repository.next_treehole_response_id(),
                post_id=post.document_id,
                author_user_id=user.document_id,
                anonymous_identity_id=anonymous.document_id,
                display_name_snapshot=anonymous.display_name,
                body_original_ciphertext=_protected_body(body),
                body_sanitized=None,
                state="checking",
                community_consent_version=user.community_consent_version or "unknown",
                deleted_at=None,
                created_at=now,
                updated_at=now,
                version=1,
            )
            saved = self.repository.create_treehole_response(response)
            projection = _response_projection(saved, viewer_id=subject.subject_id, public=False)
            self.idempotency.complete(
                reservation, status_code=200, response_digest=projection.model_dump_json()
            )
            self._audit(
                request_id,
                subject.subject_id,
                "treehole_response_create",
                saved.document_id,
                "checking",
            )
            return projection
        except RepositoryNotFound as error:
            failure = ApiException(404, "NOT_FOUND")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except ApiException as error:
            _complete_failure(self.idempotency, reservation, error)
            raise
        except Exception as error:
            failure = ApiException(500, "INTERNAL_ERROR")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error

    def delete_response(
        self,
        access_token: str,
        *,
        response_id: str,
        object_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> TreeholeDeleteResponse:
        subject = self._student(access_token)
        reservation = self.idempotency.begin(
            "student",
            subject.subject_id,
            f"/treehole/responses/{response_id}",
            idempotency_key,
            {"response_id": response_id, "object_version": object_version},
        )
        if reservation.replayed:
            return _decode_delete(reservation.record.response_digest)
        try:
            response = self.repository.get_treehole_response(response_id)
            self._check_owner(response.author_user_id, subject.subject_id)
            if response.version != object_version:
                raise ApiException(409, "VERSION_CONFLICT", current_version=response.version)
            if response.deleted_at is not None:
                raise ApiException(404, "NOT_FOUND")
            now = datetime.now(UTC)
            saved = self.repository.save_treehole_response(
                response.model_copy(
                    update={"state": "deleted", "deleted_at": now, "body_sanitized": None}
                ),
                expected_version=response.version,
            )
            result = TreeholeDeleteResponse(
                resource_id=saved.document_id,
                deleted_at=saved.deleted_at or now,
                object_version=saved.version,
            )
            self.idempotency.complete(
                reservation, status_code=200, response_digest=result.model_dump_json()
            )
            self._audit(
                request_id, subject.subject_id, "treehole_response_delete", response_id, "deleted"
            )
            return result
        except RepositoryNotFound as error:
            failure = ApiException(404, "NOT_FOUND")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except RepositoryVersionConflict as error:
            failure = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except ApiException as error:
            _complete_failure(self.idempotency, reservation, error)
            raise
        except Exception as error:
            failure = ApiException(500, "INTERNAL_ERROR")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error

    def _change_post_state(
        self,
        access_token: str,
        *,
        post_id: str,
        object_version: int,
        target: str,
        request_id: str,
        idempotency_key: str,
    ) -> TreeholeMutationResponse:
        subject = self._student(access_token)
        reservation = self.idempotency.begin(
            "student",
            subject.subject_id,
            f"/treehole/posts/{post_id}/{target}",
            idempotency_key,
            {"post_id": post_id, "object_version": object_version, "target": target},
        )
        if reservation.replayed:
            return _decode_mutation(reservation.record.response_digest)
        try:
            with self.repository.transaction():
                post = self.repository.get_treehole_post(post_id)
                self._check_owner(post.author_user_id, subject.subject_id)
                if post.version != object_version:
                    raise ApiException(409, "VERSION_CONFLICT", current_version=post.version)
                if post.deleted_at is not None:
                    raise ApiException(404, "NOT_FOUND")
                saved = self.repository.save_treehole_post(
                    post.model_copy(update={"visibility_state": target}),
                    expected_version=post.version,
                )
                result = self._mutation(saved, subject.subject_id)
            self.idempotency.complete(
                reservation, status_code=200, response_digest=result.model_dump_json()
            )
            self._audit(request_id, subject.subject_id, "treehole_post_withdraw", post_id, target)
            return result
        except RepositoryNotFound as error:
            failure = ApiException(404, "NOT_FOUND")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except RepositoryVersionConflict as error:
            failure = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except ApiException as error:
            _complete_failure(self.idempotency, reservation, error)
            raise
        except Exception as error:
            failure = ApiException(500, "INTERNAL_ERROR")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error

    def _student(self, access_token: str) -> AuthenticatedSubject:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        return subject

    def _post_projection(
        self, post: TreeholePostDocument, *, viewer_id: str, public: bool
    ) -> TreeholePostProjection:
        mine = post.author_user_id == viewer_id
        expose_body = post.visibility_state in {"published", "protected"}
        if public and not expose_body:
            expose_body = False
        responses = [
            _response_projection(response, viewer_id=viewer_id, public=public)
            for response in self.repository.list_treehole_responses(post.document_id)
            if response.deleted_at is None and (not public or response.state == "published")
        ]
        return TreeholePostProjection(
            post_id=post.document_id,
            display_name_snapshot=post.display_name_snapshot if (public or mine) else None,
            body_sanitized=post.body_sanitized if expose_body else None,
            visibility_state=post.visibility_state,
            review_state=post.review_state,
            safety_state=post.safety_state if mine else None,
            created_at=post.created_at,
            updated_at=post.updated_at,
            response_count=len(responses),
            object_version=post.version,
            mine=mine,
            responses=responses,
        )

    def _mutation(self, post: TreeholePostDocument, viewer_id: str) -> TreeholeMutationResponse:
        projection = self._post_projection(post, viewer_id=viewer_id, public=False)
        return TreeholeMutationResponse(
            post_id=post.document_id,
            visibility_state=post.visibility_state,
            review_state=post.review_state,
            display_projection=projection,
            object_version=post.version,
        )

    def _check_owner(self, owner_id: str, subject_id: str) -> None:
        if owner_id != subject_id:
            raise ApiException(404, "NOT_FOUND")

    def _audit(
        self, request_id: str, actor_id: str, action: str, resource_id: str, status: str
    ) -> None:
        try:
            self.audit.write(
                request_id=request_id,
                actor_type="student",
                actor_id=actor_id,
                capability=None,
                action=action,
                resource_type="post",
                resource_id=resource_id,
                data_scope="necessary_facts",
                outcome="success",
                reason_code=status,
                occurred_at=datetime.now(UTC),
                facts={"action_code": action, "status": status},
            )
        except Exception:
            pass


def _protected_body(body: str) -> str:
    return "enc:v1:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _contains_safety_signal(body: str) -> bool:
    return any(token in body for token in ("自杀", "自残", "不想活", "伤害自己"))


def _decode_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        value = int(cursor)
    except (TypeError, ValueError) as error:
        raise ApiException(422, "VALIDATION_FAILED") from error
    if value < 0:
        raise ApiException(422, "VALIDATION_FAILED")
    return value


def _response_projection(
    response: TreeholeResponseDocument, *, viewer_id: str, public: bool
) -> TreeholeResponseProjection:
    mine = response.author_user_id == viewer_id
    expose = response.state == "published" or mine
    return TreeholeResponseProjection(
        response_id=response.document_id,
        post_id=response.post_id,
        display_name_snapshot=response.display_name_snapshot if expose else None,
        body_sanitized=response.body_sanitized
        if expose and response.state == "published"
        else None,
        state=response.state,
        created_at=response.created_at,
        updated_at=response.updated_at,
        object_version=response.version,
    )


def _decode_mutation(value: str | None) -> TreeholeMutationResponse:
    if value is None:
        raise ApiException(500, "INTERNAL_ERROR")
    error = deserialize_api_error(value)
    if error is not None:
        raise error
    try:
        return TreeholeMutationResponse.model_validate_json(value)
    except Exception as exc:
        raise ApiException(500, "INTERNAL_ERROR") from exc


def _decode_response(value: str | None) -> TreeholeResponseProjection:
    if value is None:
        raise ApiException(500, "INTERNAL_ERROR")
    error = deserialize_api_error(value)
    if error is not None:
        raise error
    try:
        return TreeholeResponseProjection.model_validate_json(value)
    except Exception as exc:
        raise ApiException(500, "INTERNAL_ERROR") from exc


def _decode_delete(value: str | None) -> TreeholeDeleteResponse:
    if value is None:
        raise ApiException(500, "INTERNAL_ERROR")
    error = deserialize_api_error(value)
    if error is not None:
        raise error
    try:
        return TreeholeDeleteResponse.model_validate_json(value)
    except Exception as exc:
        raise ApiException(500, "INTERNAL_ERROR") from exc


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
