from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import fcm as fcm_service


async def send_push_for_notification(
    db: AsyncSession,
    *,
    user_external_id: str,
    title: str,
    body: str | None,
    article_id: uuid.UUID | None,
    topic_slug: str | None,
) -> bool:
    """Send FCM if user registered a device token and push is enabled."""
    if not fcm_service.fcm_configured():
        return False
    user = (await db.execute(select(User).where(User.external_id == user_external_id))).scalar_one_or_none()
    if not user:
        return False
    prefs = user.preferences or {}
    notif = prefs.get("notifications") or {}
    if notif.get("enabled") is False:
        return False
    if notif.get("push_enabled") is False:
        return False
    device = prefs.get("device") or {}
    token = device.get("fcm_token")
    if not token or not isinstance(token, str):
        return False

    data: dict[str, str] = {}
    if article_id:
        data["article_id"] = str(article_id)
    if topic_slug:
        data["topic_slug"] = topic_slug

    def _send() -> None:
        fcm_service.send_fcm_data_message(device_token=token, title=title, body=body, data=data or None)

    await asyncio.to_thread(_send)
    return True
