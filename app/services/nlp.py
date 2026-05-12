from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.article import Article, Category
from app.services.llm import ChatMessage, LlmError, chat_json
from app.services.sentiment import sentiment_hf_inference

PROMPT_VERSION = "v1"


def _cache_key(article_id: str, model: str, prompt_version: str) -> str:
    h = hashlib.sha256()
    h.update(article_id.encode("utf-8"))
    h.update(b"|")
    h.update(model.encode("utf-8"))
    h.update(b"|")
    h.update(prompt_version.encode("utf-8"))
    return h.hexdigest()[:32]


async def enrich_article(db: AsyncSession, article_id: str) -> dict[str, str]:
    article = (await db.execute(select(Article).where(Article.id == article_id))).scalar_one_or_none()
    if article is None:
        raise RuntimeError("Article not found.")

    if not article.body_text and not article.lead_text:
        return {}

    categories = (await db.execute(select(Category))).scalars().all()
    category_slugs = [c.slug for c in categories]
    category_slug_set = set(category_slugs)

    text = (article.body_text or article.lead_text or "")[:12000]

    versions: dict[str, str] = {}

    # 1) Summarization + categorization (LLM structured JSON)
    summary_model = settings.openai_model_summarize
    cache_key = _cache_key(str(article.id), summary_model, PROMPT_VERSION)
    if article.llm_cache_key != cache_key:
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "category_primary": {"type": ["string", "null"], "enum": category_slugs + [None]},
                "category_secondary": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "category_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "summary_short": {"type": "string", "maxLength": 800},
                "summary_long": {"type": ["string", "null"], "maxLength": 4000},
                "key_points": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            },
            "required": [
                "category_primary",
                "category_secondary",
                "category_confidence",
                "summary_short",
                "summary_long",
                "key_points",
            ],
        }

        system = (
            "You are an assistant that classifies and summarizes news articles.\n"
            "Only use information present in the article text.\n"
            "Return valid JSON that matches the provided schema exactly."
        )
        user = (
            f"Allowed categories (slugs): {', '.join(category_slugs)}\n\n"
            f"Title: {article.title}\n\n"
            f"Article:\n{text}\n"
        )

        try:
            out = await chat_json(
                model=summary_model,
                messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
                json_schema=schema,
            )
        except LlmError:
            out = None

        if out:
            primary_slug = out.get("category_primary")
            if primary_slug not in category_slug_set:
                primary_slug = None
            secondary = [s for s in (out.get("category_secondary") or []) if isinstance(s, str)]
            secondary = [s for s in secondary if s in category_slug_set and s != primary_slug][:5]

            primary_id = None
            if primary_slug:
                cat = next((c for c in categories if c.slug == primary_slug), None)
                primary_id = cat.id if cat else None

            article.category_primary_id = primary_id
            article.category_secondary = secondary
            article.category_confidence = float(out.get("category_confidence") or 0.0)
            article.summary_short = str(out.get("summary_short") or "").strip() or None
            article.summary_long = (str(out.get("summary_long")).strip() if out.get("summary_long") else None) or None
            article.summary_model = summary_model
            article.summary_prompt_version = PROMPT_VERSION
            article.llm_cache_key = cache_key
            versions["summary_model"] = summary_model
            versions["prompt_version"] = PROMPT_VERSION

    # 2) Sentiment (HF inference preferred, fallback to heuristic)
    if article.sentiment_label is None:
        try:
            label, score = await sentiment_hf_inference(text=text[:4000])
        except Exception:  # noqa: BLE001
            lower = text.lower()
            neg = sum(lower.count(w) for w in ["crisis", "death", "war", "attack", "loss"])
            pos = sum(lower.count(w) for w in ["win", "growth", "record", "success", "breakthrough"])
            if pos > neg:
                label, score = "positive", 0.55
            elif neg > pos:
                label, score = "negative", 0.55
            else:
                label, score = "neutral", 0.5
        article.sentiment_label = label
        article.sentiment_score = float(score)
        versions["sentiment"] = settings.hf_sentiment_model if settings.hf_inference_api_key else "heuristic_v1"

    await db.commit()
    return versions

