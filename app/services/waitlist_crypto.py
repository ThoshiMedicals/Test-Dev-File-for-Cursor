from __future__ import annotations

import hashlib
import hmac
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def normalize_email(email: str) -> str:
    return email.strip().lower()


def email_fingerprint(email: str) -> str:
    secret = (settings.waitlist_hmac_secret or "").encode("utf-8")
    if not secret:
        raise RuntimeError("WAITLIST_HMAC_SECRET is not configured.")
    norm = normalize_email(email)
    return hmac.new(secret, norm.encode("utf-8"), hashlib.sha256).hexdigest()


def _fernet() -> Fernet:
    key = settings.waitlist_fernet_key
    if not key:
        raise RuntimeError("WAITLIST_FERNET_KEY is not configured.")
    return Fernet(key.encode("ascii"))


def encrypt_email(email: str) -> str:
    norm = normalize_email(email)
    return _fernet().encrypt(norm.encode("utf-8")).decode("utf-8")


def decrypt_email(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("Invalid ciphertext") from e
