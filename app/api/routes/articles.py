from __future__ import annotations

import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import auth_dep, db_dep
from app.core.config import settings
from app.models.article import Article, Category, Source
from app.schemas.article import ArticleDetailOut, ArticleEnrichmentOut, ArticleIn, ArticleOut
from app.schemas.common import Envelope
from app.services.feed_intel import article_to_card
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


def _cache(response: Response) -> None:
    response.headers["Cache-Control"] = (
        f"public, max-age={settings.api_cache_control_seconds}, stale-while-revalidate=120"
    )


@router.get("", response_model=Envelope[list[dict]], dependencies=[Depends(auth_dep)])
async def list_articles(
    response: Response,
    category: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(db_dep),
) -> Envelope[list[dict]]:
    q = select(Article).options(selectinload(Article.category_primary), selectinload(Article.source))
    if category:
        q = (
            q.join(Category, Article.category_primary_id == Category.id)
            .where(Category.slug == category.strip().lower())
            .order_by(Article.published_at.desc().nullslast(), Article.ingested_at.desc())
            .offset(offset)
            .limit(limit)
        )
    else:
        q = q.order_by(Article.published_at.desc().nullslast(), Article.ingested_at.desc()).offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    _cache(response)
    return Envelope(data=[article_to_card(a) for a in rows])


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
        ingested_at=datetime.utcnow(),
        source=source_obj,
        image_url=str(payload.image_url).strip()[:2048] if payload.image_url is not None else None,
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return Envelope(data=_to_article_out(article))


@router.get("/{article_id}", response_model=Envelope[ArticleDetailOut], dependencies=[Depends(auth_dep)])
async def get_article(
    article_id: str,
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


@router.post("/{article_id}/reindex", response_model=Envelope[ArticleEnrichmentOut], dependencies=[Depends(auth_dep)])
async def reindex_article(article_id: str, db: AsyncSession = Depends(db_dep)) -> Envelope[ArticleEnrichmentOut]:
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
