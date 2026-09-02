from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request

from app.api.dependencies import bearer_token, request_id, require_idempotency_key
from app.schemas.envelope import ApiEnvelope
from app.schemas.treehole import (
    TreeholeDeleteResponse,
    TreeholeMutationResponse,
    TreeholeObjectVersionRequest,
    TreeholePostListResponse,
    TreeholePostProjection,
    TreeholePostRequest,
    TreeholeResponseProjection,
    TreeholeResponseRequest,
)

router = APIRouter(prefix="/api/v1/treehole", tags=["treehole"])
student_router = APIRouter(prefix="/api/v1", tags=["treehole"])
AuthHeader = Annotated[str | None, Header()]


@router.get("/posts")
async def list_posts(
    request: Request,
    authorization: AuthHeader = None,
    sort: str = Query(default="latest"),
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> ApiEnvelope[TreeholePostListResponse]:
    data = request.app.state.treehole_service.list_public(
        bearer_token(authorization), sort=sort, cursor=cursor, limit=limit
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/posts")
async def create_post(
    request: Request,
    body: TreeholePostRequest,
    authorization: AuthHeader = None,
) -> ApiEnvelope[TreeholeMutationResponse]:
    data = request.app.state.treehole_service.create_post(
        bearer_token(authorization),
        body=body.body,
        request_id=request_id(request),
        idempotency_key=body.client_idempotency_key,
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.get("/posts/{post_id}")
async def get_post(
    request: Request,
    post_id: str,
    authorization: AuthHeader = None,
) -> ApiEnvelope[TreeholePostProjection]:
    data = request.app.state.treehole_service.get_post(bearer_token(authorization), post_id=post_id)
    return ApiEnvelope.success(request_id(request), data=data)


@student_router.get("/me/treehole/posts")
async def list_my_posts(
    request: Request,
    authorization: AuthHeader = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> ApiEnvelope[TreeholePostListResponse]:
    data = request.app.state.treehole_service.list_mine(
        bearer_token(authorization), cursor=cursor, limit=limit
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/posts/{post_id}/withdraw")
async def withdraw_post(
    request: Request,
    post_id: str,
    body: TreeholeObjectVersionRequest,
    authorization: AuthHeader = None,
) -> ApiEnvelope[TreeholeMutationResponse]:
    data = request.app.state.treehole_service.withdraw_post(
        bearer_token(authorization),
        post_id=post_id,
        object_version=body.object_version,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.delete("/posts/{post_id}")
async def delete_post(
    request: Request,
    post_id: str,
    body: TreeholeObjectVersionRequest,
    authorization: AuthHeader = None,
) -> ApiEnvelope[TreeholeDeleteResponse]:
    data = request.app.state.treehole_service.delete_post(
        bearer_token(authorization),
        post_id=post_id,
        object_version=body.object_version,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/posts/{post_id}/responses")
async def create_response(
    request: Request,
    post_id: str,
    body: TreeholeResponseRequest,
    authorization: AuthHeader = None,
) -> ApiEnvelope[TreeholeResponseProjection]:
    data = request.app.state.treehole_service.create_response(
        bearer_token(authorization),
        post_id=post_id,
        body=body.body,
        object_version=body.object_version,
        request_id=request_id(request),
        idempotency_key=body.client_idempotency_key,
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.delete("/responses/{response_id}")
async def delete_response(
    request: Request,
    response_id: str,
    body: TreeholeObjectVersionRequest,
    authorization: AuthHeader = None,
) -> ApiEnvelope[TreeholeDeleteResponse]:
    data = request.app.state.treehole_service.delete_response(
        bearer_token(authorization),
        response_id=response_id,
        object_version=body.object_version,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data=data)
