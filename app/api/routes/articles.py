from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone

from dateutil import parser as date_parser
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import auth_dep, db_dep
from app.models.article import Article, Category, Source
from app.schemas.article import ArticleDetailOut, ArticleEnrichmentOut, ArticleIn, ArticleOut
from app.schemas.common import Envelope, EnvelopeMeta
from app.services.feed_intel import article_to_card
from app.services.related import related_by_co_engagement
from app.services.share_links import share_links_for_url

router = APIRouter(prefix="/v1/articles", tags=["articles"])


def _hash_article(url: str, title: str, body_text: str | None) -> str:
    h = hashlib.sha256()
    h.update(url.encode("utf-8"))
    h.update(b"\n")
    h.update(title.encode("utf-8"))
    if body_text:
        h.update(b"\n")
        h.update(body_text.encode("utf-8"))
    return h.hexdigest()


from app.services.http_cache import set_public_json_cache


def _cache(response: Response) -> None:
    set_public_json_cache(response)


def _encode_list_cursor(ingested_at: datetime, article_id: uuid.UUID) -> str:
    payload = {"t": ingested_at.isoformat(), "i": str(article_id)}
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_list_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    pad = "=" * (-len(cursor) % 4)
    try:
        obj = json.loads(base64.urlsafe_b64decode(cursor + pad).decode())
        t = date_parser.isoparse(obj["t"])
        i = uuid.UUID(obj["i"])
        return t, i
    except (ValueError, KeyError, json.JSONDecodeError, TypeError) as e:
        raise HTTPException(status_code=400, detail="Invalid cursor.") from e


@router.get("", response_model=Envelope[list[dict]], dependencies=[Depends(auth_dep)])
async def list_articles(
    response: Response,
    category: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    cursor: str | None = Query(None, description="Keyset cursor from `meta.next_cursor` (preferred over offset for infinite scroll)."),
    db: AsyncSession = Depends(db_dep),
) -> Envelope[list[dict]]:
    q = select(Article).options(selectinload(Article.category_primary), selectinload(Article.source))
    if category:
        q = q.join(Category, Article.category_primary_id == Category.id).where(Category.slug == category.strip().lower())
    q = q.order_by(Article.ingested_at.desc(), Article.id.desc())
    if cursor:
        t, i = _decode_list_cursor(cursor)
        q = q.where(tuple_(Article.ingested_at, Article.id) < tuple_(t, i))
    else:
        q = q.offset(offset)
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    next_cursor: str | None = None
    if rows and len(rows) == limit:
        last = rows[-1]
        next_cursor = _encode_list_cursor(last.ingested_at, last.id)
    _cache(response)
    return Envelope(data=[article_to_card(a) for a in rows], meta=EnvelopeMeta(next_cursor=next_cursor))


@router.get("/{article_id:uuid}/related", response_model=Envelope[list[dict]], dependencies=[Depends(auth_dep)])
async def list_related_articles(
    article_id: uuid.UUID,
    response: Response,
    limit: int = Query(8, ge=1, le=25),
    db: AsyncSession = Depends(db_dep),
) -> Envelope[list[dict]]:
    exists = (await db.execute(select(Article.id).where(Article.id == article_id))).scalar_one_or_none()
    if not exists:
        raise HTTPException(status_code=404, detail="Article not found.")
    data = await related_by_co_engagement(db, article_id=article_id, limit=limit)
    _cache(response)
    return Envelope(
        data=data,
        meta=EnvelopeMeta(model_versions={"method": "co_engagement_v1", "seed": str(article_id)}),
    )


@router.post("", response_model=Envelope[ArticleOut], dependencies=[Depends(auth_dep)])
async def create_article(payload: ArticleIn, db: AsyncSession = Depends(db_dep)) -> Envelope[ArticleOut]:
    url = str(payload.url)

    existing = (await db.execute(select(Article).where(Article.url == url))).scalar_one_or_none()
    if existing:
        return Envelope(data=_to_article_out(existing))

    source_obj = None
    if payload.source:
        source_obj = (await db.execute(select(Source).where(Source.name == payload.source))).scalar_one_or_none()
        if source_obj is None:
            source_obj = Source(name=payload.source)
            db.add(source_obj)

    raw_hash = _hash_article(url=url, title=payload.title, body_text=payload.body_text)
    article = Article(
        url=url,
        raw_hash=raw_hash,
        title=payload.title,
        body_text=payload.body_text,
        lead_text=payload.lead_text,
        author=payload.author,
        language=payload.language,
        published_at=payload.published_at,
        ingested_at=datetime.now(timezone.utc),
        source=source_obj,
        image_url=str(payload.image_url).strip()[:2048] if payload.image_url is not None else None,
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return Envelope(data=_to_article_out(article))


@router.get("/{article_id:uuid}", response_model=Envelope[ArticleDetailOut], dependencies=[Depends(auth_dep)])
async def get_article(
    article_id: uuid.UUID,
    response: Response,
    full: bool = Query(False, description="Include full article body text."),
    db: AsyncSession = Depends(db_dep),
) -> Envelope[ArticleDetailOut]:
    article = (
        await db.execute(
            select(Article).options(selectinload(Article.category_primary), selectinload(Article.source)).where(Article.id == article_id)
        )
    ).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found.")
    _cache(response)
    d = _to_article_out(article).model_dump()
    d["body_text"] = article.body_text if full else None
    d["share_links"] = share_links_for_url(article.url, article.title)
    return Envelope(data=ArticleDetailOut.model_validate(d))


@router.post("/{article_id:uuid}/reindex", response_model=Envelope[ArticleEnrichmentOut], dependencies=[Depends(auth_dep)])
async def reindex_article(article_id: uuid.UUID, db: AsyncSession = Depends(db_dep)) -> Envelope[ArticleEnrichmentOut]:
    article = (await db.execute(select(Article).where(Article.id == article_id))).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found.")

    return Envelope(
        data=ArticleEnrichmentOut(
            category_primary=article.category_primary.slug if article.category_primary else None,
            category_secondary=article.category_secondary or [],
            category_confidence=article.category_confidence,
            sentiment_label=article.sentiment_label,
            sentiment_score=article.sentiment_score,
            summary_short=article.summary_short,
            summary_long=article.summary_long,
            model_versions={
                "summary_model": article.summary_model or "",
                "embedding_model": article.embedding_model or "",
            },
        )
    )


def _to_article_out(article: Article) -> ArticleOut:
    return ArticleOut(
        id=article.id,
        url=article.url,
        title=article.title,
        author=article.author,
        source=article.source.name if article.source else None,
        published_at=article.published_at,
        ingested_at=article.ingested_at,
        language=article.language,
        image_url=article.image_url,
        category_primary=article.category_primary.slug if article.category_primary else None,
        category_secondary=article.category_secondary or [],
        category_confidence=article.category_confidence,
        sentiment_label=article.sentiment_label,
        sentiment_score=article.sentiment_score,
        summary_short=article.summary_short,
        summary_long=article.summary_long,
    )
