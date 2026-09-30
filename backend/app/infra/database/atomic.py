"""Shared transaction contract; adapters provide CAS through conditional updates."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol


class UnitOfWork(Protocol):
    def transaction(self) -> AbstractAsyncContextManager[None]: ...
