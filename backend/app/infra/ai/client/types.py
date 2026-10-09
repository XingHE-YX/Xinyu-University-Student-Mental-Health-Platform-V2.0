"""Provider-neutral chat requests and responses."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AIMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class AIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    model: str = Field(min_length=1)
    messages: tuple[AIMessage, ...] = Field(min_length=1)
    temperature: float = Field(default=0.2, ge=0, le=2)
    response_format: Literal["json_object", "text"] = "json_object"


class AIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str = Field(min_length=1)
    model: str | None = None
    usage: dict[str, int] | None = None
