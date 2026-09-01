"""Narrow support-resource projections for normal and safety contexts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.config.environments import EnvironmentKind
from app.config.settings import Settings
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.schemas.errors import ApiException

ResourceContext = Literal["normal", "safety"]
ResourceStatus = Literal["available", "unconfigured", "empty"]

NORMAL_ORDER = {"trusted_person": 0, "campus": 1, "emergency": 2}
SAFETY_ORDER = {"emergency": 0, "trusted_person": 1, "campus": 2}


class SupportResourceProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: str
    title: str
    description: str
    category: Literal["trusted_person", "campus", "emergency"]
    action_type: Literal["call", "copy", "open_url", "text_only"]
    action_target: str | None
    availability_text: str | None
    source_text: str
    verified_at: datetime
    version: int


class SupportResourceList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ResourceStatus
    resource_version: str | None
    resources: list[SupportResourceProjection]


class SupportResourceService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: InMemoryDomainDataRepository,
    ) -> None:
        self.settings = settings
        self.repository = repository

    def list_resources(self, *, context: str) -> SupportResourceList:
        if context not in {"normal", "safety"}:
            raise ApiException(422, "VALIDATION_FAILED")
        if self.settings.environment_kind is EnvironmentKind.UNCONFIGURED:
            return SupportResourceList(
                status="unconfigured",
                resource_version=self.settings.support_resource_version,
                resources=[],
            )
        resources = list(
            self.repository.list_support_resources(self.settings.environment_kind.value)
        )
        if not resources:
            return SupportResourceList(
                status="empty",
                resource_version=self.settings.support_resource_version,
                resources=[],
            )
        order = SAFETY_ORDER if context == "safety" else NORMAL_ORDER
        resources.sort(
            key=lambda resource: (
                order[resource.category],
                resource.sort_order,
                resource.document_id,
            )
        )
        return SupportResourceList(
            status="available",
            resource_version=self.settings.support_resource_version,
            resources=[
                SupportResourceProjection(
                    resource_id=resource.document_id,
                    title=resource.title,
                    description=resource.description,
                    category=resource.category,
                    action_type=resource.action_type,
                    action_target=resource.action_target,
                    availability_text=resource.availability_text,
                    source_text=resource.source_text,
                    verified_at=resource.verified_at,
                    version=resource.version,
                )
                for resource in resources
            ],
        )
