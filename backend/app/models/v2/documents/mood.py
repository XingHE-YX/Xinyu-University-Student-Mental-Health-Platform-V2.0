from __future__ import annotations

from datetime import datetime
from typing import Literal

from .common import (
    DocumentModel,
    LocalDateString,
    NonEmptyString,
)


class DailyMoodRecordDocument(DocumentModel):
    user_id: NonEmptyString
    record_date: LocalDateString
    mood_code: Literal["pleasant", "calm", "tired", "anxious", "low", "irritable"]
    source: Literal["mini_program"]
    deleted_at: datetime | None = None
