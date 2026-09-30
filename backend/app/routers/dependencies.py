"""HTTP request context, authentication dependencies and safe exception mapping."""

import re
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

from fastapi import Request

from app.bootstrap import Container
from app.infra.logger.common import get_logger
from app.infra.security.tokens import AuthenticatedSubject
from app.infra.serializer.error.common import ApiException

logger = get_logger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str


def create_request_id() -> str:
    return f"req_{uuid4().hex}"


def resolve_request_id(value: str | None) -> str:
    if value is None or value == "":
        return create_request_id()
    if not REQUEST_ID_PATTERN.fullmatch(value):
        raise ApiException(400, "INVALID_REQUEST", "请求编号格式不正确")
    return value


def request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else create_request_id()


def bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise ApiException(401, "AUTH_REQUIRED")
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise ApiException(401, "AUTH_REQUIRED")
    return token.strip()


async def current_subject(request: Request, authorization: str | None) -> AuthenticatedSubject:
    token = bearer_token(authorization)
    service = get_container(request).auth_service
    return await service.authenticate(token)


async def student_subject(request: Request, authorization: str | None) -> AuthenticatedSubject:
    subject = await current_subject(request, authorization)
    if subject.subject_type != "student":
        raise ApiException(403, "FORBIDDEN")
    return subject


async def admin_subject(request: Request, authorization: str | None) -> AuthenticatedSubject:
    subject = await current_subject(request, authorization)
    if subject.subject_type != "admin":
        raise ApiException(403, "FORBIDDEN")
    return subject


def require_idempotency_key(request: Request) -> str:
    value = request.headers.get("Idempotency-Key")
    if not value or len(value) > 128 or not value.strip():
        raise ApiException(400, "INVALID_REQUEST", "缺少有效的幂等键")
    return value.strip()


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


async def super_admin_subject(request: Request, authorization: str | None) -> AuthenticatedSubject:
    subject = await admin_subject(request, authorization)
    if subject.capability != "super_admin":
        raise ApiException(403, "FORBIDDEN")
    return subject
