from __future__ import annotations

import hashlib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import auth_dep, db_dep
from app.models.article import Article, Category, Source
from app.schemas.article import ArticleEnrichmentOut, ArticleIn, ArticleOut
from app.schemas.common import Envelope

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
    )
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return Envelope(data=_to_article_out(article))


@router.get("/{article_id}", response_model=Envelope[ArticleOut], dependencies=[Depends(auth_dep)])
async def get_article(article_id: str, db: AsyncSession = Depends(db_dep)) -> Envelope[ArticleOut]:
    article = (await db.execute(select(Article).where(Article.id == article_id))).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found.")
    return Envelope(data=_to_article_out(article))


@router.post("/{article_id}/reindex", response_model=Envelope[ArticleEnrichmentOut], dependencies=[Depends(auth_dep)])
async def reindex_article(article_id: str, db: AsyncSession = Depends(db_dep)) -> Envelope[ArticleEnrichmentOut]:
    article = (await db.execute(select(Article).where(Article.id == article_id))).scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found.")

    # Enrichment is executed asynchronously by workers; this endpoint returns current state.
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
        category_primary=article.category_primary.slug if article.category_primary else None,
        category_secondary=article.category_secondary or [],
        category_confidence=article.category_confidence,
        sentiment_label=article.sentiment_label,
        sentiment_score=article.sentiment_score,
        summary_short=article.summary_short,
        summary_long=article.summary_long,
    )

