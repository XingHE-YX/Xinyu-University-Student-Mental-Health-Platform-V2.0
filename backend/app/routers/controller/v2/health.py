from fastapi import APIRouter, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.models.v2.responses.health import HealthData
from app.routers.dependencies import get_container, request_id

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> ApiEnvelope[HealthData]:
    settings = get_container(request).settings
    return ApiEnvelope.success(
        request_id(request),
        HealthData(
            service="xinyu-v2-backend",
            version="0.1.0",
            environment_kind=settings.environment_kind.value,
            status="ok" if settings.configuration_status == "ready" else "degraded",
        ),
    )
