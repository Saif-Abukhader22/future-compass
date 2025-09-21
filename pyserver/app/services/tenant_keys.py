from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone, time, date
from typing import Optional, Tuple
from zoneinfo import ZoneInfo
import re

from ..db import db

try:
    # Reuse shared hashing policy for consistency
    from shared.utils.security import pwd_context
except Exception:
    # Fallback: create a local bcrypt context if shared isn't available
    from passlib.context import CryptContext  # type: ignore
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


KEY_PREFIX = os.getenv("TENANT_KEY_PREFIX", "tkn")
TZ_AMMAN = ZoneInfo("Asia/Amman")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_prefix(length: int = 8) -> str:
    # urlsafe but simple; 8 chars ~ 48 bits of entropy
    return secrets.token_urlsafe(6)[:length]


def _generate_secret(length_bytes: int = 24) -> str:
    # 24 bytes -> 32 chars base64-ish urlsafe
    return secrets.token_urlsafe(length_bytes)


def format_full_key(prefix: str, secret: str) -> str:
    return f"{KEY_PREFIX}_{prefix}_{secret}"


def parse_full_key(full_key: str) -> Optional[Tuple[str, str]]:
    try:
        parts = full_key.strip().split("_")
        if len(parts) < 3:
            return None
        # prefix like tkn_<prefix>_<secret>
        if parts[0].lower() != KEY_PREFIX.lower():
            return None
        prefix, secret = parts[1], "_".join(parts[2:])
        return prefix, secret
    except Exception:
        return None


def create_tenant_key(tenant_id: str, name: Optional[str] = None, expires_at: Optional[str] = None) -> str:
    """
    Create a new tenant API key and persist only its hash. Returns the full key string once.
    """
    prefix = _generate_prefix()
    secret = _generate_secret()
    key_hash = pwd_context.hash(secret)
    # Normalize expiry to Asia/Amman local time ISO string (with offset)
    norm_exp = normalize_expires_at(expires_at)
    db.createTenantApiKeyRecord(tenant_id, prefix, key_hash, name=name, expires_at=norm_exp)
    return format_full_key(prefix, secret)


def verify_tenant_key(full_key: str) -> Optional[str]:
    """
    Verify a provided full key. Returns tenant_id on success, otherwise None.
    """
    parsed = parse_full_key(full_key)
    if not parsed:
        return None
    prefix, secret = parsed
    rec = db.getTenantApiKeyRecordByPrefix(prefix)
    if not rec:
        return None
    if int(rec.get("revoked", 0)) == 1:
        return None
    exp = rec.get("expires_at")
    if exp:
        try:
            exp_str = exp.replace("Z", "+00:00")
            exp_dt = datetime.fromisoformat(exp_str)
            # If stored naive (shouldn't happen), assume Amman time
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=TZ_AMMAN)
            if exp_dt < datetime.now(timezone.utc):
                return None
        except Exception:
            # If bad format, ignore expiration
            pass
    key_hash = rec.get("key_hash") or ""
    try:
        if pwd_context.verify(secret, key_hash):
            return rec.get("tenant_id")
    except Exception:
        return None
    return None


def revoke_tenant_key(prefix: str) -> bool:
    return db.revokeTenantApiKey(prefix)


def normalize_expires_at(expires_at: Optional[str]) -> Optional[str]:
    """
    Normalize incoming expiry to Asia/Amman local time ISO string (with offset).
    Accepts:
      - ISO date: YYYY-MM-DD (treated as that day's 23:59:59 in Amman)
      - ISO datetime (with or without timezone). If tz-aware, converted to Amman time.
      - Returns None if input is falsy.
    """
    if not expires_at:
        return None
    s = expires_at.strip()
    # Date-only pattern
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        try:
            d = date.fromisoformat(s)
            dt_local = datetime.combine(d, time(23, 59, 59)).replace(tzinfo=TZ_AMMAN)
            return dt_local.isoformat()
        except Exception:
            return s  # fallback
    # Datetime: replace trailing Z if present
    s2 = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_AMMAN)
        else:
            dt = dt.astimezone(TZ_AMMAN)
        return dt.isoformat()
    except Exception:
        return s

