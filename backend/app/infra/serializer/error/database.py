"""Persistence failures shared by all database implementations."""

from app.infra.serializer.error.common import AppError, ErrorCode


class RepositoryError(AppError):
    code = ErrorCode.REPOSITORY_UNAVAILABLE


class RepositoryNotFound(RepositoryError):
    code = ErrorCode.REPOSITORY_NOT_FOUND


class RepositoryVersionConflict(RepositoryError):
    code = ErrorCode.REPOSITORY_VERSION_CONFLICT

    def __init__(self, current_version: int | None) -> None:
        self.current_version = current_version
        super().__init__("document version conflict")

    def log_fields(self) -> dict[str, str | int | None]:
        return {**super().log_fields(), "current_version": self.current_version}


class RepositoryUnavailable(RepositoryError):
    pass


class RepositoryCommitUncertain(RepositoryUnavailable):
    """A write may have committed; callers must reconcile rather than retry blindly."""


class RepositoryCommitUnknown(RepositoryUnavailable):
    """Commit was sent but its result could not be confirmed."""

    code = ErrorCode.REPOSITORY_COMMIT_UNKNOWN
