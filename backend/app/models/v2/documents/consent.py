from __future__ import annotations

from datetime import datetime
from typing import Literal

from .common import (
    DocumentModel,
    FixedVersionOne,
    NonEmptyString,
)


class ConsentEventDocument(DocumentModel):
    version: FixedVersionOne = 1
    user_id: NonEmptyString
    consent_kind: Literal["base_service", "community_content"]
    action: Literal["accepted", "withdrawn"]
    document_version: NonEmptyString
    source: Literal["mini_program", "admin_seed", "migration"]
    occurred_at: datetime
    request_id: NonEmptyString
