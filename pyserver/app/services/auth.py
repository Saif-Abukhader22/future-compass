from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from fastapi import HTTPException

from jose import jwt, JWTError, ExpiredSignatureError
from passlib.context import CryptContext

from ..config import settings


# Password hashing: support both argon2 and bcrypt, verify any
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(password, hashed)
    except Exception:
        return False


# JWT helpers (separate secrets for AT/RT)
ALGORITHM = "HS256"


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_jwt(payload: Dict[str, Any]) -> str:
    # Access token
    minutes = int(os.getenv("ACCESS_TOKEN_MINUTES", str(getattr(settings, "ACCESS_TOKEN_MINUTES", 60))))
    exp = _now() + timedelta(minutes=minutes)
    data = {**payload, "iat": _now(), "exp": exp, "token_type": "access"}
    secret = os.getenv("JWT_AT_SECRET", getattr(settings, "JWT_AT_SECRET", "dev-at-secret"))
    return jwt.encode(data, secret, algorithm=ALGORITHM)


def decode_jwt(token: str) -> Optional[Dict[str, Any]]:
    try:
        secret = os.getenv("JWT_AT_SECRET", getattr(settings, "JWT_AT_SECRET", "dev-at-secret"))
        data = jwt.decode(token, secret, algorithms=[ALGORITHM])
        if data.get("token_type") not in (None, "access"):
            # If token_type present, ensure it's access
            return None
        return data
    except (ExpiredSignatureError, JWTError):
        return None


def create_refresh_jwt(payload: Dict[str, Any]) -> str:
    days = int(os.getenv("REFRESH_TOKEN_DAYS", str(getattr(settings, "REFRESH_TOKEN_DAYS", 30))))
    exp = _now() + timedelta(days=days)
    data = {**payload, "iat": _now(), "exp": exp, "token_type": "refresh"}
    secret = os.getenv("JWT_RT_SECRET", getattr(settings, "JWT_RT_SECRET", "dev-rt-secret"))
    return jwt.encode(data, secret, algorithm=ALGORITHM)


def decode_refresh_jwt(token: str) -> Optional[Dict[str, Any]]:
    try:
        secret = os.getenv("JWT_RT_SECRET", getattr(settings, "JWT_RT_SECRET", "dev-rt-secret"))
        data = jwt.decode(token, secret, algorithms=[ALGORITHM])
        if data.get("token_type") != "refresh":
            return None
        return data
    except (ExpiredSignatureError, JWTError):
        return None


# Password reset token helpers
def create_password_reset_token(email: str, minutes: int = 15) -> str:
    exp = _now() + timedelta(minutes=minutes)
    payload = {"email": email, "iat": _now(), "exp": exp, "token_type": "password_reset"}
    secret = os.getenv("JWT_RESET_SECRET") or os.getenv("JWT_AT_SECRET", getattr(settings, "JWT_AT_SECRET", "dev-at-secret"))
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_password_reset_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        secret = os.getenv("JWT_RESET_SECRET") or os.getenv("JWT_AT_SECRET", getattr(settings, "JWT_AT_SECRET", "dev-at-secret"))
        data = jwt.decode(token, secret, algorithms=[ALGORITHM])
        if data.get("token_type") != "password_reset":
            return None
        return data
    except (ExpiredSignatureError, JWTError):
        return None


# reCAPTCHA helper aligned with identity_service behavior
def verify_recaptcha(token: Optional[str]) -> bool:
    disabled = str(os.getenv("RECAPTCHA_DISABLED", "1")).lower() in {"1", "true", "yes"}
    if disabled:
        return True
    if not token:
        raise HTTPException(status_code=400, detail="recaptcha_failed")
    secret = os.getenv("RECAPTCHA_SECRET_KEY")
    if not secret:
        # If not configured, fail closed
        raise HTTPException(status_code=400, detail="recaptcha_failed")
    try:
        import httpx  # type: ignore
    except Exception:
        # httpx not installed; recommend disabling recaptcha in env for local
        raise HTTPException(status_code=400, detail="recaptcha_failed")
    try:
        url = "https://www.google.com/recaptcha/api/siteverify"
        with httpx.Client() as client:
            resp = client.post(url, data={"secret": secret, "response": token})
            data = resp.json()
            if not data.get("success"):
                raise HTTPException(status_code=400, detail="recaptcha_failed")
        return True
    except HTTPException:
        raise
    except Exception:
        # Network or unexpected error
        raise HTTPException(status_code=400, detail="recaptcha_failed")
