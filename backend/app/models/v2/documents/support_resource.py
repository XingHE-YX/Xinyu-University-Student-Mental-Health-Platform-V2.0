from __future__ import annotations

from datetime import datetime
from typing import Literal

from .common import (
    DocumentModel,
    NonEmptyString,
    NonNegativeInt,
)


class SupportResourceDocument(DocumentModel):
    environment_scope: Literal["demo", "authorized"]
    resource_set_version: NonEmptyString
    category: Literal["trusted_person", "campus", "emergency"]
    title: NonEmptyString
    description: NonEmptyString
    action_type: Literal["call", "copy", "open_url", "text_only"]
    action_target: str | None = None
    availability_text: str | None = None
    source_text: NonEmptyString
    verified_at: datetime
    expires_at: datetime | None = None
    enabled: bool
    sort_order: NonNegativeInt
