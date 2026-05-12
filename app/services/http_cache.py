from __future__ import annotations

from fastapi import Response

from app.core.config import settings


def set_public_json_cache(response: Response) -> None:
    """Browser + CDN friendly headers (Cloudflare honors s-maxage on the edge)."""
    ma = max(0, int(settings.api_cache_control_seconds))
    parts = [f"public, max-age={ma}", "stale-while-revalidate=120"]
    sm = settings.cdn_s_maxage_seconds
    if sm is not None and int(sm) > 0:
        parts.append(f"s-maxage={int(sm)}")
    response.headers["Cache-Control"] = ", ".join(parts)


def set_private_json_cache(response: Response) -> None:
    """User-specific JSON: do not store on shared CDN caches."""
    response.headers["Cache-Control"] = "private, max-age=30, stale-while-revalidate=60"
