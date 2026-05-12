from __future__ import annotations

from typing import Any

import httpx
from dateutil import parser as date_parser

from app.core.config import settings
from app.schemas.fetched_article import FetchedArticle


def _normalize_image(raw: str | None) -> str | None:
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s or s.lower() == "none":
        return None
    if s.startswith("//"):
        s = "https:" + s
    if not s.startswith("http"):
        return None
    return s[:2048]


def _article_url(item: dict[str, Any]) -> str | None:
    u = item.get("url")
    if isinstance(u, str) and u.strip().startswith("http"):
        return u.strip()[:2048]
    urls = item.get("urls")
    if isinstance(urls, str) and urls.strip().startswith("http"):
        return urls.strip()[:2048]
    if isinstance(urls, list) and urls:
        first = urls[0]
        if isinstance(first, str) and first.strip().startswith("http"):
            return first.strip()[:2048]
    return None


async def fetch_currents_latest(*, language: str | None = None) -> list[FetchedArticle]:
    if not settings.currents_api_key:
        raise RuntimeError("CURRENTS_API_KEY is not configured.")

    lang = (language or settings.currents_language).strip()[:8] or "en"
    url = "https://api.currentsapi.services/v1/latest-news"
    headers = {"Authorization": settings.currents_api_key}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers, params={"language": lang})
        if r.status_code >= 400:
            raise RuntimeError(f"Currents API error {r.status_code}: {r.text}")
        data = r.json()

    if data.get("status") != "ok":
        raise RuntimeError(f"Currents API unexpected payload: {data}")

    out: list[FetchedArticle] = []
    for a in data.get("news") or []:
        if not isinstance(a, dict):
            continue
        u = _article_url(a)
        if not u:
            continue
        title = (a.get("title") or u)[:1024]
        desc = a.get("description")
        lead = str(desc).strip()[:8000] if isinstance(desc, str) else None
        author = a.get("author")
        author_s = str(author)[:256] if isinstance(author, str) else None
        pub = a.get("published")
        published_at = None
        if isinstance(pub, str):
            try:
                published_at = date_parser.parse(pub)
            except (ValueError, TypeError):
                published_at = None
        cats = a.get("category")
        source_hint = None
        if isinstance(cats, list) and cats and isinstance(cats[0], str):
            source_hint = str(cats[0])[:256]
        elif isinstance(cats, str):
            source_hint = cats[:256]
        img = _normalize_image(a.get("image") if isinstance(a.get("image"), str) else None)
        out.append(
            FetchedArticle(
                url=u,
                title=title,
                lead_text=lead,
                image_url=img,
                source_name=author_s or source_hint,
                published_at=published_at,
                author=author_s,
            )
        )
    return out


def currents_status() -> dict[str, Any]:
    return {"configured": bool(settings.currents_api_key), "language": settings.currents_language}
