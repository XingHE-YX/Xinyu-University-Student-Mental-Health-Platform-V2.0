from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.infra.config.settings import Settings


def register_cors(app: FastAPI, settings: Settings) -> None:
    if settings.admin_web_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.admin_web_origins),
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
            allow_headers=["Authorization", "Content-Type", "X-Request-Id", "Idempotency-Key"],
            expose_headers=["X-Request-Id"],
            allow_credentials=False,
        )
