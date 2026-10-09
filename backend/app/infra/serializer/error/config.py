from app.infra.serializer.error.common import AppError, ErrorCode


class ConfigurationError(AppError):
    code = ErrorCode.CONFIGURATION_ERROR


class EnvironmentMismatchError(ConfigurationError):
    pass
