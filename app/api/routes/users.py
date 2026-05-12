from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import auth_dep, db_dep
from app.models.notification import UserNotification
from app.models.user import User, UserEvent
from app.services.recs import apply_bandit_reward, recommend_for_user
from app.schemas.common import Envelope
from app.schemas.user import (
    NotificationCreateIn,
    NotificationOut,
    RecommendationsOut,
    UserEventIn,
    UserOut,
    UserUpsertIn,
)

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.post("", response_model=Envelope[UserOut], dependencies=[Depends(auth_dep)])
async def upsert_user(payload: UserUpsertIn, db: AsyncSession = Depends(db_dep)) -> Envelope[UserOut]:
    user = (await db.execute(select(User).where(User.external_id == payload.external_id))).scalar_one_or_none()
    if user is None:
        user = User(
            external_id=payload.external_id,
            preferences=payload.preferences,
            personalization_opt_in=payload.personalization_opt_in,
            tone_preference=payload.tone_preference,
        )
        db.add(user)
    else:
        user.preferences = payload.preferences
        user.personalization_opt_in = payload.personalization_opt_in
        user.tone_preference = payload.tone_preference

    await db.commit()
    await db.refresh(user)
    return Envelope(data=_to_user_out(user))


@router.get("/{external_id}", response_model=Envelope[UserOut], dependencies=[Depends(auth_dep)])
async def get_user(external_id: str, db: AsyncSession = Depends(db_dep)) -> Envelope[UserOut]:
    user = (await db.execute(select(User).where(User.external_id == external_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return Envelope(data=_to_user_out(user))


@router.post("/{external_id}/events", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def post_events(external_id: str, events: list[UserEventIn], db: AsyncSession = Depends(db_dep)) -> Envelope[dict]:
    for e in events:
        if e.user_external_id != external_id:
            raise HTTPException(status_code=400, detail="Event user_external_id mismatch.")
        db.add(
            UserEvent(
                user_external_id=e.user_external_id,
                article_id=e.article_id,
                event_type=e.event_type,
                value=e.value,
                meta=e.meta,
            )
        )
        # Update bandit on explicit engagement events if the client passes arm name in meta.
        if e.event_type in ("click", "save", "share"):
            await apply_bandit_reward(
                db,
                user_external_id=external_id,
                arm_name=str(e.meta.get("bandit_arm")) if isinstance(e.meta, dict) else None,
                reward=1.0,
            )
        elif e.event_type in ("dismiss",):
            await apply_bandit_reward(
                db,
                user_external_id=external_id,
                arm_name=str(e.meta.get("bandit_arm")) if isinstance(e.meta, dict) else None,
                reward=-1.0,
            )
    await db.commit()
    return Envelope(data={"accepted": len(events)})


@router.get("/{external_id}/recommendations", response_model=Envelope[RecommendationsOut], dependencies=[Depends(auth_dep)])
async def get_recommendations(external_id: str, limit: int = 50, db: AsyncSession = Depends(db_dep)) -> Envelope[RecommendationsOut]:
    items, versions = await recommend_for_user(db, user_external_id=external_id, limit=limit)
    return Envelope(data=RecommendationsOut(user_external_id=external_id, items=items, model_versions=versions))


@router.get("/{external_id}/notifications", response_model=Envelope[list[NotificationOut]], dependencies=[Depends(auth_dep)])
async def list_notifications(
    external_id: str,
    unread_only: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(db_dep),
) -> Envelope[list[NotificationOut]]:
    base = select(UserNotification).where(UserNotification.user_external_id == external_id)
    if unread_only:
        base = base.where(UserNotification.read_at.is_(None))
    q = base.order_by(desc(UserNotification.created_at)).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return Envelope(data=[_to_notification_out(n) for n in rows])


@router.post("/{external_id}/notifications", response_model=Envelope[NotificationOut], dependencies=[Depends(auth_dep)])
async def create_notification(
    external_id: str,
    payload: NotificationCreateIn,
    db: AsyncSession = Depends(db_dep),
) -> Envelope[NotificationOut]:
    prefs = (await db.execute(select(User).where(User.external_id == external_id))).scalar_one_or_none()
    if prefs is None:
        raise HTTPException(status_code=404, detail="User not found.")
    notif_prefs = (prefs.preferences or {}).get("notifications") or {}
    if notif_prefs.get("enabled") is False:
        raise HTTPException(status_code=400, detail="Notifications disabled for this user.")
    topics = notif_prefs.get("topics") or []
    if topics and payload.topic_slug and payload.topic_slug not in topics:
        raise HTTPException(status_code=400, detail="Topic not in user subscription list.")

    n = UserNotification(
        user_external_id=external_id,
        title=payload.title,
        body=payload.body,
        topic_slug=payload.topic_slug,
        severity=payload.severity,
        article_id=payload.article_id,
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)
    return Envelope(data=_to_notification_out(n))


@router.patch("/{external_id}/notifications/{notification_id}/read", response_model=Envelope[NotificationOut], dependencies=[Depends(auth_dep)])
async def mark_notification_read(
    external_id: str,
    notification_id: str,
    db: AsyncSession = Depends(db_dep),
) -> Envelope[NotificationOut]:
    n = (
        await db.execute(
            select(UserNotification).where(UserNotification.id == notification_id).where(UserNotification.user_external_id == external_id)
        )
    ).scalar_one_or_none()
    if n is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    n.read_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(n)
    return Envelope(data=_to_notification_out(n))


@router.get("/{external_id}/export", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def export_user_data(external_id: str, db: AsyncSession = Depends(db_dep)) -> Envelope[dict]:
    user = (await db.execute(select(User).where(User.external_id == external_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    events = (
        await db.execute(select(UserEvent).where(UserEvent.user_external_id == external_id).order_by(UserEvent.created_at.desc()).limit(5000))
    ).scalars().all()
    return Envelope(
        data={
            "user": _to_user_out(user).model_dump(),
            "events": [
                {
                    "id": str(e.id),
                    "article_id": str(e.article_id),
                    "event_type": e.event_type,
                    "created_at": e.created_at.isoformat(),
                    "value": e.value,
                    "meta": e.meta,
                }
                for e in events
            ],
        }
    )


@router.delete("/{external_id}", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def delete_user_data(external_id: str, db: AsyncSession = Depends(db_dep)) -> Envelope[dict]:
    await db.execute(delete(UserNotification).where(UserNotification.user_external_id == external_id))
    await db.execute(delete(UserEvent).where(UserEvent.user_external_id == external_id))
    result = await db.execute(delete(User).where(User.external_id == external_id))
    await db.commit()
    return Envelope(data={"deleted": int(result.rowcount or 0)})


def _to_notification_out(n: UserNotification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        title=n.title,
        body=n.body,
        topic_slug=n.topic_slug,
        severity=n.severity,
        article_id=n.article_id,
        read_at=n.read_at,
        created_at=n.created_at,
    )


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        external_id=user.external_id,
        created_at=user.created_at,
        preferences=user.preferences or {},
        personalization_opt_in=user.personalization_opt_in,
        tone_preference=user.tone_preference,
    )

