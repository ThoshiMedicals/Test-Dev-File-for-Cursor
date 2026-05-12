from __future__ import annotations

from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, logger


def create_app() -> FastAPI:
    configure_logging(settings.environment)
    app = FastAPI(title=settings.app_name)
    app.include_router(api_router)

    Instrumentator().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

    @app.middleware("http")
    async def audit_middleware(request: Request, call_next):
        response = await call_next(request)
        logger.info(
            "request",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            client_host=request.client.host if request.client else None,
        )
        return response

    return app


app = create_app()

