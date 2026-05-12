from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from dateutil import parser as date_parser

from app.core.config import settings


@dataclass
class FetchedArticle:
    url: str
    title: str
    lead_text: str | None
    image_url: str | None
    source_name: str | None
    published_at: datetime | None
    author: str | None


async def fetch_top_headlines(*, country: str | None = None, page_size: int | None = None) -> list[FetchedArticle]:
    if not settings.news_api_key:
        raise RuntimeError("NEWS_API_KEY is not configured.")

    c = country or settings.news_api_country
    ps = page_size or settings.news_api_page_size
    url = "https://newsapi.org/v2/top-headlines"
    params = {"country": c, "pageSize": min(ps, 100), "apiKey": settings.news_api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params)
        if r.status_code >= 400:
            raise RuntimeError(f"NewsAPI error {r.status_code}: {r.text}")
        data = r.json()

    if data.get("status") != "ok":
        raise RuntimeError(f"NewsAPI unexpected payload: {data}")

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


def newsapi_status() -> dict[str, Any]:
    return {"configured": bool(settings.news_api_key), "country": settings.news_api_country}
