"""The single response envelope shared by every HTTP endpoint."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

from app.schemas.errors import ApiError

DataT = TypeVar("DataT")


class ApiEnvelope(BaseModel, Generic[DataT]):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    data: DataT | None = None
    error: ApiError | None = None

    @classmethod
    def success(cls, request_id: str, data: DataT) -> "ApiEnvelope[DataT]":
        return cls(request_id=request_id, data=data, error=None)

    @classmethod
    def failure(cls, request_id: str, error: ApiError) -> "ApiEnvelope[DataT]":
        return cls(request_id=request_id, data=None, error=error)
