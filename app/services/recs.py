from __future__ import annotations

import math
import os
import pickle
import random
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.article import Article
from app.models.user import BanditState, User, UserEvent
from app.services.feed_intel import engagement_hotness
from app.services.llm import embed_text

ALS_ARTIFACT_PATH = os.path.join("ml", "artifacts", "als.pkl")


def _cosine(a: list[float], b: list[float]) -> float:
    av = np.asarray(a, dtype=np.float32)
    bv = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(av) * np.linalg.norm(bv))
    if denom <= 1e-9:
        return 0.0
    return float(np.dot(av, bv) / denom)


def _age_hours(dt: datetime | None) -> float:
    if dt is None:
        return 1e9
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 3600.0)


def _recency_score(hours: float) -> float:
    return float(math.exp(-hours / 24.0))


def effective_tone_preference(user: User) -> str | None:
    prefs = user.preferences or {}
    sp = prefs.get("sentiment_preference")
    if isinstance(sp, str):
        x = sp.strip().lower()
        if x in ("any", "all", "mixed", ""):
            pass
        elif x in ("positive", "neutral", "negative", "positive_or_neutral"):
            return x
    return user.tone_preference


def _preferred_category_slugs(user: User) -> set[str]:
    prefs = user.preferences or {}
    raw = prefs.get("preferred_categories")
    if not isinstance(raw, list):
        return set()
    return {str(x).strip().lower() for x in raw if isinstance(x, str) and str(x).strip()}


def _sentiment_match(user_tone: str | None, article_sentiment: str | None) -> float:
    if not user_tone or not article_sentiment:
        return 0.0
    if user_tone == "positive_or_neutral":
        return 1.0 if article_sentiment in ("positive", "neutral") else -1.0
    if user_tone == "neutral":
        return 1.0 if article_sentiment == "neutral" else -0.5
    if user_tone == article_sentiment:
        return 1.0
    return -0.25


def _default_arms() -> list[dict]:
    # Small set of weight presets. Bandit learns which re-ranking works best.
    return [
        {"name": "balanced", "w": {"recency": 0.35, "popularity": 0.25, "personal": 0.35, "tone": 0.05}, "a": 2, "b": 2},
        {"name": "recency_heavy", "w": {"recency": 0.55, "popularity": 0.15, "personal": 0.25, "tone": 0.05}, "a": 2, "b": 2},
        {"name": "personal_heavy", "w": {"recency": 0.20, "popularity": 0.20, "personal": 0.55, "tone": 0.05}, "a": 2, "b": 2},
        {"name": "popularity_heavy", "w": {"recency": 0.20, "popularity": 0.55, "personal": 0.20, "tone": 0.05}, "a": 2, "b": 2},
    ]


async def _get_or_create_bandit(db: AsyncSession, user_external_id: str) -> BanditState:
    state = (await db.execute(select(BanditState).where(BanditState.user_external_id == user_external_id))).scalar_one_or_none()
    if state is None:
        state = BanditState(user_external_id=user_external_id, arms=_default_arms())
        db.add(state)
        await db.commit()
        await db.refresh(state)
    if not state.arms:
        state.arms = _default_arms()
        await db.commit()
    return state


def _sample_arm(arms: list[dict]) -> dict:
    # Thompson sampling: sample p ~ Beta(a, b).
    best = None
    best_p = -1.0
    for arm in arms:
        a = max(1, int(arm.get("a", 1)))
        b = max(1, int(arm.get("b", 1)))
        p = random.betavariate(a, b)
        if p > best_p:
            best_p = p
            best = arm
    return best or arms[0]


async def ensure_article_embedding(db: AsyncSession, article: Article) -> None:
    if article.embedding is not None:
        return
    text = (article.lead_text or article.body_text or article.title or "")[:8000]
    vec = await embed_text(model=settings.openai_model_embed, text=text)
    article.embedding = vec
    article.embedding_model = settings.openai_model_embed
    await db.commit()


async def ensure_user_profile(db: AsyncSession, user: User) -> None:
    if user.profile_embedding is not None:
        return

    # Build profile from recent positive engagement.
    rows = (
        await db.execute(
            select(UserEvent.article_id)
            .where(UserEvent.user_external_id == user.external_id)
            .where(UserEvent.event_type.in_(["click", "save", "dwell", "share", "like"]))
            .order_by(UserEvent.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    if not rows:
        return

    articles = (
        await db.execute(select(Article).where(Article.id.in_(rows)).where(Article.embedding.is_not(None)))
    ).scalars().all()
    if not articles:
        return

    mat = np.asarray([a.embedding for a in articles if a.embedding], dtype=np.float32)
    if mat.size == 0:
        return
    profile = np.mean(mat, axis=0)
    user.profile_embedding = profile.tolist()
    user.profile_updated_at = datetime.now(timezone.utc)
    await db.commit()


async def recommend_for_user(db: AsyncSession, user_external_id: str, limit: int = 50) -> tuple[list[dict], dict[str, str]]:
    user = (await db.execute(select(User).where(User.external_id == user_external_id))).scalar_one_or_none()
    if user is None:
        user = User(external_id=user_external_id)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    if not user.personalization_opt_in:
        items, versions = await _popular_feed(db, user=user, limit=limit)
        return items, versions

    # Candidates: recent articles.
    candidates = (
        await db.execute(
            select(Article)
            .options(selectinload(Article.category_primary))
            .order_by(Article.published_at.desc().nullslast(), Article.ingested_at.desc())
            .limit(400)
        )
    ).scalars().all()

    # Ensure embeddings on a bounded subset.
    for a in candidates[:120]:
        if a.embedding is None and settings.openai_api_key:
            try:
                await ensure_article_embedding(db, a)
            except Exception:  # noqa: BLE001
                pass

    await ensure_user_profile(db, user)

    hot = await engagement_hotness(db, hours=24)

    bandit = await _get_or_create_bandit(db, user_external_id=user_external_id)
    arm = _sample_arm(bandit.arms)
    w = arm.get("w") or {}

    pref_cats = _preferred_category_slugs(user)
    tone_pref = effective_tone_preference(user)

    scored: list[tuple[float, Article]] = []
    for a in candidates:
        age = _age_hours(a.published_at or a.ingested_at)
        rec = _recency_score(age)
        pop = math.log1p(hot.get(str(a.id), 0.0))
        pers = 0.0
        if user.profile_embedding and a.embedding:
            pers = _cosine(user.profile_embedding, a.embedding)
        tone = _sentiment_match(tone_pref, a.sentiment_label)
        cat_boost = (
            1.22
            if pref_cats and a.category_primary and a.category_primary.slug.lower() in pref_cats
            else 1.0
        )

        score = cat_boost * (
            float(w.get("recency", 0.35)) * rec
            + float(w.get("popularity", 0.25)) * pop
            + float(w.get("personal", 0.35)) * pers
            + float(w.get("tone", 0.05)) * tone
        )
        scored.append((score, a))

    scored.sort(key=lambda x: x[0], reverse=True)
    items = [
        {
            "article_id": str(a.id),
            "score": float(s),
            "url": a.url,
            "title": a.title,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "category_primary": a.category_primary.slug if a.category_primary else None,
            "sentiment": a.sentiment_label,
        }
        for (s, a) in scored[:limit]
    ]

    versions = {
        "bandit_arm": str(arm.get("name", "")),
        "embedding_model": settings.openai_model_embed if settings.openai_api_key else "",
        "recs": "content_based_v2",
    }
    return items, versions


async def _popular_feed(db: AsyncSession, user: User, limit: int) -> tuple[list[dict], dict[str, str]]:
    # Minimal fallback: most recent articles, lightly filtered by tone preference.
    rows = (
        await db.execute(
            select(Article)
            .options(selectinload(Article.category_primary))
            .order_by(Article.published_at.desc().nullslast(), Article.ingested_at.desc())
            .limit(300)
        )
    ).scalars().all()
    filtered = []
    tone_pref = effective_tone_preference(user)
    for a in rows:
        if tone_pref and a.sentiment_label:
            if _sentiment_match(tone_pref, a.sentiment_label) < 0:
                continue
        filtered.append(a)
        if len(filtered) >= limit:
            break
    items = [{"article_id": str(a.id), "url": a.url, "title": a.title} for a in filtered]
    return items, {"recs": "popular_v1"}


def load_als_artifact() -> dict | None:
    if not os.path.exists(ALS_ARTIFACT_PATH):
        return None
    with open(ALS_ARTIFACT_PATH, "rb") as f:
        return pickle.load(f)


async def apply_bandit_reward(
    db: AsyncSession,
    *,
    user_external_id: str,
    arm_name: str | None,
    reward: float,
) -> None:
    if not arm_name:
        return
    state = await _get_or_create_bandit(db, user_external_id=user_external_id)
    changed = False
    for arm in state.arms:
        if arm.get("name") != arm_name:
            continue
        a = int(arm.get("a", 1))
        b = int(arm.get("b", 1))
        if reward > 0:
            arm["a"] = a + 1
        else:
            arm["b"] = b + 1
        changed = True
        break
    if changed:
        await db.commit()

