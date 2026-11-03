import base64
import hashlib
import json
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet
from fastapi import HTTPException
from pwdlib import PasswordHash

from .settings import settings

password_hasher = PasswordHash.recommended()
_dummy_hash = password_hasher.hash(secrets.token_urlsafe(24))
_attempts: dict[str, list[float]] = {}
_attempt_lock = threading.Lock()


def verify_password(password: str, encoded: str | None):
    return password_hasher.verify(password, encoded or _dummy_hash) and encoded is not None


def issue_token(user, device_id: int | None = None):
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": str(user.id), "ver": user.token_version, "did": device_id,
        "iat": now, "exp": now + timedelta(minutes=settings().access_token_minutes),
        "iss": "motordesk", "aud": "motordesk-app",
    }, settings().secret_key, algorithm="HS256")


def decode_token(token: str):
    try:
        return jwt.decode(token, settings().secret_key, algorithms=["HS256"], audience="motordesk-app", issuer="motordesk")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, "Sesión inválida o expirada", headers={"WWW-Authenticate": "Bearer"}) from exc


def throttle_login(key: str):
    now = time.monotonic()
    with _attempt_lock:
        if len(_attempts) > 10000:
            expired = [k for k, values in _attempts.items() if not values or values[-1] < now - 60]
            for item in expired:
                del _attempts[item]
            if len(_attempts) > 10000:
                raise HTTPException(429, "Demasiados intentos; intente en un minuto")
        values = [value for value in _attempts.get(key, []) if value > now - 60]
        if len(values) >= 5:
            raise HTTPException(429, "Demasiados intentos; intente en un minuto")
        _attempts[key] = [*values, now]


def cipher():
    key = base64.urlsafe_b64encode(hashlib.sha256(settings().secret_key.encode()).digest())
    return Fernet(key)


def encrypt_payload(payload: dict):
    return cipher().encrypt(json.dumps(payload).encode()).decode()


def decrypt_payload(payload: str):
    return json.loads(cipher().decrypt(payload.encode()))
