from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.core.logging import logger


def send_plain_email(*, to_addr: str, subject: str, body: str) -> bool:
    """
    Best-effort SMTP send for breaking-news or digest alerts.
    Returns False when SMTP is not configured or send fails.
    """
    if not settings.smtp_host or not settings.smtp_from:
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_addr
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            if settings.smtp_user and settings.smtp_password:
                smtp.starttls()
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("email_send_failed", error=str(e), to=to_addr)
        return False
