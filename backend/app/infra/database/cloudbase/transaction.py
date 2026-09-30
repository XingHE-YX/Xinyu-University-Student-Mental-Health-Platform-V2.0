"""Bounded rollback and explicit uncertain outcomes for native transactions."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from urllib.parse import quote

import anyio

from app.infra.database.common import (
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)
from app.infra.logger.common import get_logger
from app.infra.serializer.error.database import RepositoryCommitUncertain

if TYPE_CHECKING:
    from app.infra.database.cloudbase.client import CloudBaseStore


@asynccontextmanager
async def transaction(store: CloudBaseStore) -> AsyncIterator[None]:
    if store._transaction.get() is not None:
        yield
        return
    data = await store.request("POST", "/transactions", in_transaction=False)
    transaction_id = data.get("transactionId")
    if not isinstance(transaction_id, str) or not transaction_id:
        raise RepositoryUnavailable("CloudBase transaction ID is missing")
    token = store._transaction.set(transaction_id)
    path = f"/transactions/{quote(transaction_id, safe='')}"
    try:
        yield
        try:
            await store.request("POST", path + "/commit", in_transaction=False)
        except RepositoryUnavailable:
            raise RepositoryCommitUncertain("CloudBase commit outcome is unknown") from None
    except BaseException:
        with anyio.CancelScope(shield=True):
            with anyio.move_on_after(store.config.rollback_timeout_seconds):
                try:
                    await store.request("POST", path + "/rollback", in_transaction=False)
                except RepositoryUnavailable, RepositoryNotFound, RepositoryVersionConflict:
                    get_logger(__name__).error("transaction_rollback_failed")
        raise
    finally:
        store._transaction.reset(token)
