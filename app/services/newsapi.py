from __future__ import annotations

from typing import Any

import httpx
from dateutil import parser as date_parser

from app.core.config import settings
from app.schemas.fetched_article import FetchedArticle


class NewsAPIError(Exception):
    """Raised when NewsAPI returns a non-success payload or HTTP error."""

    def __init__(self, message: str, *, http_status: int | None = None, api_code: str | None = None):
        super().__init__(message)
        self.http_status = http_status
        self.api_code = api_code


def _raise_from_payload(data: dict[str, Any], http_status: int) -> None:
    if data.get("status") == "ok":
        return
    code = data.get("code")
    msg = data.get("message") or str(data)
    text = f"NewsAPI error: {msg}"
    if code == "apiKeyInvalid" or http_status == 401:
        raise NewsAPIError(text, http_status=http_status, api_code=str(code) if code else "unauthorized")
    if code == "apiKeyMissing":
        raise NewsAPIError(text, http_status=http_status, api_code="apiKeyMissing")
    if code in ("maximumResultsReached", "rateLimited"):
        raise NewsAPIError(text, http_status=http_status, api_code=str(code))
    raise NewsAPIError(text, http_status=http_status, api_code=str(code) if code else None)


async def fetch_top_headlines(*, country: str | None = None, page_size: int | None = None) -> list[FetchedArticle]:
    if not settings.news_api_key:
        raise NewsAPIError("NEWS_API_KEY is not configured.", api_code="not_configured")

    c = country or settings.news_api_country
    ps = page_size or settings.news_api_page_size
    url = "https://newsapi.org/v2/top-headlines"
    params = {"country": c, "pageSize": min(ps, 100), "apiKey": settings.news_api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params)
        try:
            data = r.json()
        except Exception as e:  # noqa: BLE001
            raise NewsAPIError(f"NewsAPI returned non-JSON body (HTTP {r.status_code}).", http_status=r.status_code) from e

    if r.status_code >= 400:
        if isinstance(data, dict):
            _raise_from_payload(data, r.status_code)
        raise NewsAPIError(f"NewsAPI HTTP {r.status_code}: {r.text[:500]}", http_status=r.status_code)

    if not isinstance(data, dict):
        raise NewsAPIError("NewsAPI returned unexpected JSON.", http_status=r.status_code)

    _raise_from_payload(data, r.status_code)

    out: list[FetchedArticle] = []
    for a in data.get("articles") or []:
        if not isinstance(a, dict):
            continue
        u = a.get("url")
        if not u or not isinstance(u, str):
            continue
        title = (a.get("title") or u)[:1024]
        desc = a.get("description")
        lead = str(desc).strip()[:8000] if isinstance(desc, str) else None
        img = a.get("urlToImage")
        image_url = str(img).strip()[:2048] if isinstance(img, str) and img.startswith("http") else None
        src = a.get("source") or {}
        source_name = src.get("name") if isinstance(src, dict) else None
        pub = a.get("publishedAt")
        published_at = None
        if isinstance(pub, str):
            try:
                published_at = date_parser.parse(pub)
            except (ValueError, TypeError):
                published_at = None
        author = a.get("author")
        author_s = str(author)[:256] if isinstance(author, str) else None
        out.append(
            FetchedArticle(
                url=u.strip()[:2048],
                title=title,
                lead_text=lead,
                image_url=image_url,
                source_name=str(source_name)[:256] if source_name else None,
                published_at=published_at,
                author=author_s,
            )
        )
    return out


async def validate_news_api_key() -> dict[str, Any]:
    """Lightweight call to verify credentials (page size 1)."""
    if not settings.news_api_key:
        return {"ok": False, "code": "not_configured", "message": "NEWS_API_KEY is not set."}
    url = "https://newsapi.org/v2/top-headlines"
    params = {"country": settings.news_api_country, "pageSize": 1, "apiKey": settings.news_api_key}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        try:
            data = r.json()
        except Exception:
            return {"ok": False, "http_status": r.status_code, "message": "Non-JSON response."}
    if not isinstance(data, dict):
        return {"ok": False, "http_status": r.status_code, "message": "Unexpected payload."}
    if data.get("status") != "ok":
        return {
            "ok": False,
            "http_status": r.status_code,
            "code": data.get("code"),
            "message": data.get("message") or str(data),
        }
    return {"ok": True, "http_status": r.status_code, "sample_articles": len(data.get("articles") or [])}


def newsapi_status() -> dict[str, Any]:
    return {"configured": bool(settings.news_api_key), "country": settings.news_api_country}
