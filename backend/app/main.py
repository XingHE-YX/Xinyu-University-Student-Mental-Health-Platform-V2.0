from fastapi import FastAPI
from pydantic import BaseModel


class HealthData(BaseModel):
    service: str
    version: str
    environment_kind: str
    status: str


class HealthResponse(BaseModel):
    request_id: str
    data: HealthData
    error: None = None


app = FastAPI(title="心语 V2 API", version="0.1.0")


@app.get("/api/v1/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Return a dependency-free service health response for local and CloudBase checks."""

    return HealthResponse(
        request_id="health-check",
        data=HealthData(
            service="xinyu-v2-backend",
            version="0.1.0",
            environment_kind="demo",
            status="ok",
        ),
    )
