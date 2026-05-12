from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_dep
from app.constants.waitlist import ALLOWED_INTERESTS
from app.models.waitlist import WaitlistInteraction, WaitlistSubscriber
from app.schemas.common import Envelope
from app.schemas.waitlist import (
    WaitlistConfigOut,
    WaitlistInteractionIn,
    WaitlistInteractionOut,
    WaitlistSubscribeIn,
    WaitlistSubscribeOut,
)
from app.services.sentiment import sentiment_hf_inference
from app.services.waitlist_crypto import email_fingerprint, encrypt_email
from app.services.waitlist_signals import sentiment_from_reaction
from app.core.logging import logger

router = APIRouter(prefix="/v1/waitlist", tags=["waitlist"])


@router.get("/config", response_model=Envelope[WaitlistConfigOut])
async def waitlist_config() -> Envelope[WaitlistConfigOut]:
    return Envelope(data=WaitlistConfigOut(interests=sorted(ALLOWED_INTERESTS)))


async def _sentiment_for_text(text: str) -> tuple[str, float]:
    t = text.strip()
    if not t:
        return "neutral", 0.0
    try:
        return await sentiment_hf_inference(t[:4000])
    except Exception:  # noqa: BLE001
        lower = t.lower()
        neg = sum(lower.count(w) for w in ["bad", "hate", "slow", "confusing", "never", "spam"])
        pos = sum(lower.count(w) for w in ["love", "great", "excited", "thanks", "awesome", "can't wait"])
        if pos > neg:
            return "positive", 0.6
        if neg > pos:
            return "negative", 0.6
        return "neutral", 0.5


@router.post("/subscribe", response_model=Envelope[WaitlistSubscribeOut])
async def waitlist_subscribe(payload: WaitlistSubscribeIn, db: AsyncSession = Depends(db_dep)) -> Envelope[WaitlistSubscribeOut]:
    try:
        fp = email_fingerprint(payload.email)
        ciphertext = encrypt_email(str(payload.email))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    interests = [i.strip().lower() for i in payload.interests if i.strip()]
    invalid = [i for i in interests if i not in ALLOWED_INTERESTS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown interests: {invalid}")

    existing = (await db.execute(select(WaitlistSubscriber).where(WaitlistSubscriber.email_fingerprint == fp))).scalar_one_or_none()
    if existing:
        return Envelope(
            data=WaitlistSubscribeOut(
                id=existing.id,
                status="already_subscribed",
                interests=existing.interests or [],
                sentiment_label=existing.sentiment_label,
                sentiment_score=existing.sentiment_score,
                message="You are already on the list. We will keep you posted.",
            )
        )

    sent_label: str | None = None
    sent_score: float | None = None
    if payload.optional_feedback and payload.optional_feedback.strip():
        sent_label, sent_score = await _sentiment_for_text(payload.optional_feedback)

    sub = WaitlistSubscriber(
        email_ciphertext=ciphertext,
        email_fingerprint=fp,
        interests=interests,
        session_id=(payload.session_id.strip()[:64] if payload.session_id else None),
        optional_feedback=payload.optional_feedback,
        sentiment_label=sent_label,
        sentiment_score=sent_score,
        consent_marketing=payload.consent_marketing,
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    try:
        from workers.tasks.waitlist import enrich_waitlist_subscriber

        enrich_waitlist_subscriber.delay(str(sub.id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("waitlist_enrich_enqueue_failed", error=str(exc), subscriber_id=str(sub.id))

    return Envelope(
        data=WaitlistSubscribeOut(
            id=sub.id,
            status="subscribed",
            interests=interests,
            sentiment_label=sent_label,
            sentiment_score=sent_score,
            message="Thanks — you will hear from us soon.",
        )
    )


@router.post("/interactions", response_model=Envelope[list[WaitlistInteractionOut]])
async def waitlist_interactions(events: list[WaitlistInteractionIn], db: AsyncSession = Depends(db_dep)) -> Envelope[list[WaitlistInteractionOut]]:
    if len(events) > 100:
        raise HTTPException(status_code=400, detail="Too many events in one request.")

    out: list[WaitlistInteractionOut] = []
    for ev in events:
        sent_label: str | None = None
        sent_score: float | None = None

        if ev.event_type in ("reaction", "quick_reaction", "emoji_reaction"):
            emoji_val = None
            if isinstance(ev.meta, dict):
                emoji_val = ev.meta.get("emoji") if ev.meta.get("emoji") is not None else ev.meta.get("label")
            inferred = sentiment_from_reaction(str(emoji_val) if emoji_val is not None else None)
            if inferred:
                sent_label, sent_score = inferred
        elif ev.event_type == "feedback_blur" and isinstance(ev.meta, dict):
            text = ev.meta.get("text")
            if isinstance(text, str) and text.strip():
                sent_label, sent_score = await _sentiment_for_text(text)

        row = WaitlistInteraction(
            session_id=ev.session_id.strip()[:64],
            event_type=ev.event_type.strip()[:64],
            meta=ev.meta or {},
            sentiment_label=sent_label,
            sentiment_score=sent_score,
        )
        db.add(row)
        await db.flush()
        out.append(
            WaitlistInteractionOut(
                id=row.id,
                created_at=row.created_at,
                sentiment_label=sent_label,
                sentiment_score=sent_score,
            )
        )

    await db.commit()
    return Envelope(data=out)
