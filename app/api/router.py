from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.articles import router as articles_router
from app.api.routes.feed import router as feed_router
from app.api.routes.health import router as health_router
from app.api.routes.users import router as users_router
from app.api.routes.waitlist import router as waitlist_router

from app.api.routes.integrations import router as integrations_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(articles_router)
api_router.include_router(users_router)
api_router.include_router(feed_router)
api_router.include_router(waitlist_router)
api_router.include_router(integrations_router)

