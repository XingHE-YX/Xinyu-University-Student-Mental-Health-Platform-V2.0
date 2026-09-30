from __future__ import annotations

from typing import Literal

from pydantic import model_validator

from .common import (
    DocumentModel,
    LocalDateString,
    NonEmptyString,
    NonNegativeInt,
)


class QuoteEntryDocument(DocumentModel):
    quote_text: NonEmptyString
    author_text: NonEmptyString
    work_text: str | None = None
    source_kind: Literal["public_domain", "project_original", "copyright_pending"]
    source_url: NonEmptyString
    language_version: NonEmptyString
    review_status: Literal["待核验", "已核验", "已启用", "已停用"]
    rights_note: NonEmptyString
    enabled: bool
    display_from: LocalDateString | None = None
    display_until: LocalDateString | None = None
    sort_order: NonNegativeInt
    library_version: NonEmptyString

    @model_validator(mode="after")
    def validate_enabled_rights(self) -> QuoteEntryDocument:
        if self.enabled and self.source_kind == "copyright_pending":
            raise ValueError("copyright pending quotes cannot be enabled")
        return self
