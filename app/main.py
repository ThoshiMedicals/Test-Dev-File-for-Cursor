from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, logger


def create_app() -> FastAPI:
    configure_logging(settings.environment)
    app = FastAPI(title=settings.app_name)
    app.include_router(api_router)

    static_root = Path(__file__).resolve().parent.parent / "static"
    coming_soon = static_root / "coming-soon" / "index.html"
    feed_page = static_root / "feed" / "index.html"

    if static_root.exists():
        app.mount("/static", StaticFiles(directory=str(static_root)), name="static")

    @app.get("/news")
    async def news_feed_page() -> FileResponse:
        if not feed_page.is_file():
            raise HTTPException(status_code=404, detail="News feed UI not found.")
        return FileResponse(feed_page, media_type="text/html; charset=utf-8")

    @app.get("/")
    async def root_feed() -> FileResponse:
        """Homepage: live news feed (Coming Soon waitlist stays at `/coming-soon`)."""
        if not feed_page.is_file():
            raise HTTPException(status_code=404, detail="News feed UI not found.")
        return FileResponse(feed_page, media_type="text/html; charset=utf-8")

    @app.get("/coming-soon")
    async def coming_soon_page() -> FileResponse:
        if not coming_soon.is_file():
            raise HTTPException(status_code=404, detail="Coming Soon page not found.")
        return FileResponse(coming_soon, media_type="text/html; charset=utf-8")

    if settings.environment == "dev":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

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

