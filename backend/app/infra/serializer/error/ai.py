from app.infra.serializer.error.common import AppError, ErrorCode


class AIUnavailable(AppError):
    code = ErrorCode.AI_UNAVAILABLE


class DeepSeekUnavailable(AIUnavailable):
    """DeepSeek-specific failure with the common AI error contract."""
