"""Stable API errors and their user-readable Chinese messages."""

from typing import Any

from pydantic import BaseModel, ConfigDict

ERROR_MESSAGES: dict[str, str] = {
    "INVALID_REQUEST": "请求内容不正确，请检查后重试",
    "AUTH_REQUIRED": "请先完成登录",
    "SESSION_EXPIRED": "会话已过期，请重新登录",
    "CONSENT_REQUIRED": "完成相关同意后才能继续",
    "IDENTITY_REQUIRED": "完成身份核验后才能继续",
    "FORBIDDEN": "当前账号没有执行此操作的权限",
    "NOT_FOUND": "暂时找不到这项内容",
    "VERSION_CONFLICT": "内容刚刚发生变化，请刷新后查看最新状态",
    "IDEMPOTENCY_CONFLICT": "这次请求编号已用于另一项操作，请重新提交",
    "VALIDATION_FAILED": "提交内容不符合要求，请检查后重试",
    "SAFETY_CONFIRMATION_REQUIRED": "请先完成安全确认，再继续查看结果",
    "SAFETY_SUPPORT_BLOCKED": "当前安全支持流程尚未完成，暂时不能继续",
    "RATE_LIMITED": "操作太频繁了，请稍后再试",
    "INTERNAL_ERROR": "服务暂时出现问题，请稍后再试",
    "DEPENDENCY_UNAVAILABLE": "相关服务暂时不可用，请稍后再试",
}

RETRYABLE_CODES = {
    "INTERNAL_ERROR",
    "DEPENDENCY_UNAVAILABLE",
    "RATE_LIMITED",
}


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retryable: bool = False
    current_version: int | str | None = None


class ApiException(Exception):
    """An expected failure that can safely cross the HTTP boundary."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str | None = None,
        *,
        retryable: bool | None = None,
        current_version: int | str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, ERROR_MESSAGES["INTERNAL_ERROR"])
        self.retryable = code in RETRYABLE_CODES if retryable is None else retryable
        self.current_version = current_version
        super().__init__(self.message)

    def to_error(self) -> ApiError:
        return ApiError(
            code=self.code,
            message=self.message,
            retryable=self.retryable,
            current_version=self.current_version,
        )


def status_error(status_code: int) -> ApiException:
    mapping = {
        400: "INVALID_REQUEST",
        401: "AUTH_REQUIRED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "VERSION_CONFLICT",
        422: "VALIDATION_FAILED",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        503: "DEPENDENCY_UNAVAILABLE",
    }
    return ApiException(status_code, mapping.get(status_code, "INTERNAL_ERROR"))


def safe_validation_error() -> ApiException:
    return ApiException(422, "VALIDATION_FAILED")


def safe_error_payload(error: ApiException) -> dict[str, Any]:
    return error.to_error().model_dump()
