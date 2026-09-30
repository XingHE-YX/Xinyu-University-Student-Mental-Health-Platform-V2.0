from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

NonEmptyString = Annotated[str, Field(min_length=1)]

VersionInt = Annotated[int, Field(ge=1)]

NonNegativeInt = Annotated[int, Field(ge=0)]

LocalDateString = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]

FixedVersionOne = Literal[1]


class DocumentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    document_id: NonEmptyString = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    version: VersionInt
