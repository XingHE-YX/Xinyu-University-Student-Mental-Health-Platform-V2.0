"""Daily quote selection from the configured local quote library."""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from app.domain.models import QuoteEntryDocument
from app.repositories.domain_data_repository import InMemoryDomainDataRepository

SHANGHAI = ZoneInfo("Asia/Shanghai")


class QuoteProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote_id: str
    quote_text: str
    author_text: str
    work_text: str | None
    library_version: str


class QuoteSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["available", "unconfigured"]
    quote: QuoteProjection | None


class QuoteService:
    def __init__(
        self,
        *,
        repository: InMemoryDomainDataRepository,
        choice_provider: Callable[[tuple[QuoteEntryDocument, ...]], QuoteEntryDocument]
        | None = None,
    ) -> None:
        self.repository = repository
        self._choice_provider = choice_provider or random.choice

    def get_daily_quote(
        self,
        *,
        now: datetime | None = None,
        previous_quote_id: str | None = None,
    ) -> QuoteSelection:
        current_date = _shanghai_date(now or datetime.now(UTC))
        entries = self.repository.list_available_quote_entries(record_date=current_date)
        if not entries:
            return QuoteSelection(status="unconfigured", quote=None)
        eligible = tuple(entry for entry in entries if entry.document_id != previous_quote_id)
        selected = self._choice_provider(eligible or entries)
        return QuoteSelection(
            status="available",
            quote=QuoteProjection(
                quote_id=selected.document_id,
                quote_text=selected.quote_text,
                author_text=selected.author_text,
                work_text=selected.work_text,
                library_version=selected.library_version,
            ),
        )


def _shanghai_date(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(SHANGHAI).date().isoformat()
