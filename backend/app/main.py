"""ASGI entrypoint; resource assembly and routes live in their owning modules."""

from typing import Unpack

from fastapi import FastAPI

from app.bootstrap import Overrides, build_container, install_container, lifespan
from app.infra.config.settings import Settings
from app.infra.serializer.handlers import register_exception_handlers
from app.routers.middleware.access_log import AccessLogMiddleware
from app.routers.middleware.cors import register_cors
from app.routers.middleware.request_context import RequestContextMiddleware
from app.routers.router import router


def create_app(settings: Settings | None = None, **overrides: Unpack[Overrides]) -> FastAPI:
    container = build_container(settings, **overrides)
    app = FastAPI(title="心语 V2 API", version="0.1.0", lifespan=lifespan)
    install_container(app, container)
    register_exception_handlers(app)
    register_cors(app, container.settings)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(router)
    return app


app = create_app()
