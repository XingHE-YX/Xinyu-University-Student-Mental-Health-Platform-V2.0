"""Repository contracts shared by CloudBase and local test implementations."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

JsonDocument = dict[str, Any]


@dataclass(frozen=True, slots=True)
class DocumentPage:
    items: tuple[JsonDocument, ...]
    next_cursor: str | None


class RepositoryError(RuntimeError):
    """Base class for errors that must be mapped at the API boundary."""


class RepositoryNotFound(RepositoryError):
    """The requested document does not exist in the current environment."""


class RepositoryVersionConflict(RepositoryError):
    """The document version changed before a conditional update."""

    def __init__(self, current_version: int | None) -> None:
        self.current_version = current_version
        super().__init__("document version conflict")


class RepositoryUnavailable(RepositoryError):
    """CloudBase or another persistence dependency cannot be reached."""


class DocumentRepository(Protocol):
    def query(
        self,
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> DocumentPage: ...

    def conditional_update(
        self,
        collection: str,
        document_id: str,
        *,
        expected_version: int,
        updates: Mapping[str, Any],
    ) -> JsonDocument: ...

    def logical_delete(
        self,
        collection: str,
        document_id: str,
        *,
        expected_version: int,
    ) -> JsonDocument: ...
