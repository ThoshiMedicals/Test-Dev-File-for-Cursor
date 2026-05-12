from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from app.core.config import settings
from app.core.logging import logger

_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


def fcm_configured() -> bool:
    return bool(settings.firebase_credentials_path and Path(settings.firebase_credentials_path).is_file())


def _project_id_from_file(path: str) -> str:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    pid = data.get("project_id")
    if not pid:
        raise ValueError("Service account JSON missing project_id (Firebase project).")
    return str(pid)


def _get_access_token() -> tuple[str, str]:
    """Return (access_token, project_id)."""
    path = settings.firebase_credentials_path or ""
    creds = service_account.Credentials.from_service_account_file(path, scopes=[_FCM_SCOPE])
    creds.refresh(Request())
    if not creds.token:
        raise RuntimeError("Could not obtain OAuth token for FCM.")
    return creds.token, _project_id_from_file(path)


def send_fcm_data_message(*, device_token: str, title: str, body: str | None, data: dict[str, str] | None = None) -> dict[str, Any]:
    """
    Send one FCM HTTP v1 notification. Caller must run from threadpool if invoked from async code.
    Raises on transport/API errors.
    """
    if not fcm_configured():
        raise RuntimeError("FCM is not configured (set FIREBASE_CREDENTIALS_PATH to a service account JSON).")

    token, project_id = _get_access_token()
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    payload: dict[str, Any] = {
        "message": {
            "token": device_token,
            "notification": {"title": title[:256], "body": (body or "")[:2000]},
        }
    }
    if data:
        payload["message"]["data"] = {k: str(v)[:1024] for k, v in data.items()}

    with httpx.Client(timeout=20) as client:
        r = client.post(url, json=payload, headers={"Authorization": f"Bearer {token}"})
    if r.status_code >= 400:
        logger.warning("fcm_send_failed", status=r.status_code, text=r.text[:500])
        r.raise_for_status()
    return r.json()
