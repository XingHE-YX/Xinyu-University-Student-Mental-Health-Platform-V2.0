from app.infra.serializer.error.common import AppError, ErrorCode


class DeepSeekUnavailable(AppError):
    code = ErrorCode.AI_UNAVAILABLE


class AIUnavailable(DeepSeekUnavailable):
    """Provider-independent AI failure, retained under a common public type."""
