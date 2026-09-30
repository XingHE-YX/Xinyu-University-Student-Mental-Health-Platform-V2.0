from pydantic import BaseModel


class HealthData(BaseModel):
    service: str
    version: str
    environment_kind: str
    status: str
