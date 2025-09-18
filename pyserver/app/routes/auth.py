from __future__ import annotations

import os
import traceback
import logging
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi import status
from fastapi import UploadFile, File  # placeholders for parity with identity_service
from fastapi.security import OAuth2PasswordRequestForm
from starlette.responses import JSONResponse
import re
from pydantic import BaseModel, Field, EmailStr
from pydantic import TypeAdapter

from ..db import db
from ..config import settings
from ..services.auth import (
    hash_password,
    verify_password,
    create_jwt,
    decode_jwt,
    create_refresh_jwt,
    decode_refresh_jwt,
    verify_recaptcha,
    create_password_reset_token,
    decode_password_reset_token,
)
from ..services.verification_email import send_verification_email, send_password_reset_email_shared
from ..services.tenant_keys import create_tenant_key, parse_full_key, revoke_tenant_key


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/auth", tags=["auth"]) 


class SignupBody(BaseModel):
    email: EmailStr = Field(description="Valid email address")
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)


class UserCreate(BaseModel):
    # Mirrors identity_service.schemas.user.UserCreate shape (subset for pyserver)
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    recaptcha_token: str
    country_id: int | None = None


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class RegistrationConfirmation(BaseModel):
    email: EmailStr
    verificationCode: str = Field(min_length=4, max_length=10)
    recaptcha_token: str | None = None


class EmailData(BaseModel):
    email: EmailStr
    recaptcha_token: str | None = None


class TokenData(BaseModel):
    access_token: str


class ForgotPasswordBody(BaseModel):
    email: EmailStr
    recaptcha_token: str | None = None


class ResetPasswordBody(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=200)

class ResendResetBody(BaseModel):
    token: str


class CreateTenantKeyBody(BaseModel):
    name: str | None = None
    expires_at: str | None = None  # ISO8601 UTC


class RevokeTenantKeyBody(BaseModel):
    prefix: str = Field(min_length=1)


_email_adapter = TypeAdapter(EmailStr)


def _normalize_email(raw: str) -> str:
    try:
        return _email_adapter.validate_python((raw or "").strip().lower())
    except Exception:
        raise HTTPException(status_code=400, detail=_error_payload(
            code="invalid_email", message="Email is invalid", field="email"
        ))


REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days


def _set_refresh_cookie(resp: Response, token: str):
    # Use secure cookies except in local/dev environments
    env = os.getenv("ENVIRONMENT") or getattr(settings, "ENVIRONMENT", None) or os.getenv("PY_ENV")
    secure_flag = False if (env is None or str(env).lower() in {"local", "development", "dev"}) else True
    resp.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=secure_flag,
        samesite="lax",
        path="/",
    )


def _debug_enabled() -> bool:
    # Prefer settings flag; fall back to environment variable
    try:
        return bool(getattr(settings, "AUTH_DEBUG", 0)) or os.getenv("AUTH_DEBUG") == "1"
    except Exception:
        return os.getenv("AUTH_DEBUG") == "1"


# Note: Avoid logging passwords or emails in server logs.


def _error_payload(code: str, message: str, field: str | None = None, hint: str | None = None, extra: dict | None = None):
    payload = {"code": code, "message": message}
    if field:
        payload["field"] = field
    if hint:
        payload["hint"] = hint
    if extra and _debug_enabled():
        payload["debug"] = extra
    return payload


def _password_issues(password: str) -> list[str]:
    issues: list[str] = []
    if len(password) < 8:
        issues.append("Must be at least 8 characters long")
    if re.search(r"\s", password):
        issues.append("Remove spaces; password cannot contain whitespace")
    if not re.search(r"[a-z]", password):
        issues.append("Add a lowercase letter (a-z)")
    if not re.search(r"[A-Z]", password):
        issues.append("Add an uppercase letter (A-Z)")
    if not re.search(r"\d", password):
        issues.append("Add a number (0-9)")
    if not re.search(r"[^A-Za-z0-9]", password):
        issues.append("Add a symbol (!@#$%^&* etc.)")
    return issues


@router.post("/tenant-keys", summary="Create a tenant API key (returns secret once)")
def create_tenant_key_route(req: Request, body: CreateTenantKeyBody):
    tenant_id = getattr(req.state, "tenant_id", None) or req.headers.get("x-tenant-id") or "dev-tenant"
    # Create and return full key; caller must store it client-side
    key = create_tenant_key(tenant_id, name=body.name, expires_at=body.expires_at)
    # Return the prefix too for later management
    parsed = parse_full_key(key)
    prefix = parsed[0] if parsed else None
    return {"key": key, "prefix": prefix}


@router.post("/tenant-keys/revoke", summary="Revoke a tenant API key by prefix")
def revoke_tenant_key_route(body: RevokeTenantKeyBody):
    ok = revoke_tenant_key(body.prefix)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Key not found"})
    return {"ok": True}

class KeyLoginBody(BaseModel):
    key: str = Field(min_length=16)
    displayName: str | None = Field(default=None, min_length=1, max_length=100)


@router.post("/tenant-login", summary="enter the users using auth key", tags=["auth"])
def tenant_login_auth_key(req: Request, body: KeyLoginBody, response: Response):
    """
    Exchange a Tenant Authentication Key (tkn_...) for a standard session.
    - Validates key format, revocation, and expiry
    - Verifies secret against stored hash
    - Creates/reuses a user bound to this key
    - Returns access token; sets rotated refresh cookie
    """
    try:
        raw_key = (body.key or "").strip()
        parsed = parse_full_key(raw_key)
        if not parsed or not isinstance(parsed, (list, tuple)) or len(parsed) < 2:
            raise HTTPException(status_code=400, detail=_error_payload(
                code="invalid_key", message="Authentication key is malformed"
            ))

        prefix, secret = parsed[0], parsed[1]
        if not prefix or not secret:
            raise HTTPException(status_code=400, detail=_error_payload(
                code="invalid_key", message="Authentication key is invalid"
            ))

        # Fetch the key record by prefix (expects: id, tenantId, secret_hash, revoked, expires_at)
        key_rec = getattr(db, "getTenantKeyByPrefix", lambda *_: None)(prefix)
        if not key_rec:
            # Do not reveal whether the key exists beyond a generic message
            raise HTTPException(status_code=403, detail=_error_payload(
                code="invalid_key", message="Authentication key is invalid"
            ))

        # Block revoked keys
        if getattr(key_rec, "revoked", False):
            raise HTTPException(status_code=403, detail=_error_payload(
                code="key_revoked", message="Authentication key has been revoked"
            ))

        # Check expiry, if present
        from datetime import datetime, timezone
        exp_iso = getattr(key_rec, "expires_at", None)
        if exp_iso:
            try:
                exp_dt = datetime.fromisoformat(exp_iso)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if exp_dt < datetime.now(timezone.utc):
                    raise HTTPException(status_code=403, detail=_error_payload(
                        code="key_expired", message="Authentication key has expired"
                    ))
            except HTTPException:
                raise
            except Exception:
                if _debug_enabled():
                    logger.warning("Invalid expires_at on key %s", getattr(key_rec, "id", None))

        # Verify the key's secret against stored hash
        stored_hash = getattr(key_rec, "secret_hash", None)
        if not stored_hash or not verify_password(secret, stored_hash):
            raise HTTPException(status_code=403, detail=_error_payload(
                code="invalid_key", message="Authentication key is invalid"
            ))

        # Ensure tenant exists
        tenant_id = getattr(key_rec, "tenantId", None) or getattr(key_rec, "tenant_id", None)
        if not tenant_id:
            raise HTTPException(status_code=500, detail=_error_payload(
                code="invalid_key_record", message="Key record missing tenant"
            ))
        tenant = db.upsertTenant(tenant_id, tenant_id)

        # Create or reuse a durable user bound to this key
        key_id = getattr(key_rec, "id", None) or prefix  # prefix as fallback stable id
        display = (body.displayName or "").strip()
        user = getattr(db, "getOrCreateAuthKeyUser")(tenant.id, key_id, display)

        # Success: mint tokens and set refresh cookie
        token = create_jwt({"sub": user.id, "tenant": tenant.id, "email": getattr(user, "email", None)})
        refresh = create_refresh_jwt({"sub": user.id, "tenant": tenant.id})
        _set_refresh_cookie(response, refresh)

        # Match your TokenData shape
        return TokenData(access_token=token)

    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"/tenant-login error: {e}\n{tb}")
        detail = {"code": "internal_error", "message": "Failed to authenticate with key"}
        if _debug_enabled():
            detail["debug"] = str(e)
            detail["trace"] = tb
        raise HTTPException(status_code=500, detail=detail)


@router.post("/signup")
def signup(req: Request, body: SignupBody, response: Response):
    try:
        tenant_id = req.headers.get("x-tenant-id") or "dev-tenant"
        tenant = db.upsertTenant(tenant_id, tenant_id)
        # Normalize inputs (accept `name` as display name)
        display = (body.name or "").strip()
        if not display:
            raise HTTPException(status_code=422, detail=_error_payload(
                code="invalid_name", message="Name is required", field="name"
            ))
        # Enforce password quality
        issues = _password_issues(body.password)
        if issues:
            raise HTTPException(
                status_code=422,
                detail=_error_payload(
                    code="weak_password",
                    message="Password does not meet requirements",
                    field="password",
                    extra={"issues": issues},
                ),
            )

        normalized_email = _normalize_email(str(body.email))
        existing = db.getUserByEmail(tenant.id, normalized_email)
        if existing:
            raise HTTPException(
                status_code=409,
                detail=_error_payload(
                    code="email_taken",
                    message="Email already registered",
                    field="email",
                    hint="Try logging in or use a different email",
                    extra={"email": normalized_email},
                ),
            )

        # Create user with hashed password (email unconfirmed) and send code
        pwd_hash = hash_password(body.password)
        user = db.createUserWithAuthEmail(tenant.id, normalized_email, display, "", pwd_hash, 0)
        import random
        from datetime import timedelta, timezone, datetime as dt
        code = f"{random.randint(100000, 999999)}"
        exp = (dt.now(tz=timezone.utc) + timedelta(minutes=15)).isoformat()
        db.setUserVerification(user.id, code, exp)

        # Attempt to send the verification email; always log to console and try provider
        try:
            send_verification_email(normalized_email, code, name=display)
        except Exception as mail_err:
            # Log but do not fail signup; optionally expose in debug
            logger.warning(f"Failed to send verification email: {mail_err}")

        detail = {"status": "verification_sent", "message": "A verification code was sent to your email. Please verify to activate your account."}
        if _debug_enabled():
            detail["debug"] = {"verificationCode": code}
        return JSONResponse(status_code=201, content=detail)
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"/signup error: {e}\n{tb}")
        detail = {"code": "internal_error", "message": "Failed to sign up"}
        if _debug_enabled():
            detail["debug"] = str(e)
            detail["trace"] = tb
        raise HTTPException(status_code=500, detail=detail)


@router.post("/login", response_model=TokenData)
async def login(req: Request, response: Response, body: LoginBody | None = None):
    try:
        tenant_id = req.headers.get("x-tenant-id") or "dev-tenant"
        tenant = db.upsertTenant(tenant_id, tenant_id)
        # Accept both JSON and OAuth2PasswordRequestForm (username/password)
        email: str | None = None
        password: str | None = None
        try:
            ctype = (req.headers.get("content-type") or "").lower()
            if "application/x-www-form-urlencoded" in ctype or "multipart/form-data" in ctype:
                form = await req.form()
                email = str(form.get("username") or form.get("email") or "")
                password = str(form.get("password") or "")
            elif body is not None:
                email = str(body.email)
                password = body.password
        except Exception:
            pass
        if not email or not password:
            raise HTTPException(status_code=400, detail=_error_payload(
                code="invalid_request", message="email/username and password required"
            ))
        # Validate and normalize email; trim password
        email = _normalize_email(email)
        password = password.strip()
        if not password:
            raise HTTPException(status_code=400, detail=_error_payload(
                code="invalid_password", message="Password is required", field="password"
            ))
        user = db.getUserByEmail(tenant.id, email)
        if not user:
            # identity_service returns 400 for invalid login
            raise HTTPException(status_code=400, detail="login_invalid_error")
        # Require email confirmation before login; resend code automatically and signal client to show verification UI
        if not (user.email_confirmed or False):
            import random
            from datetime import timedelta, timezone, datetime as dt
            code = f"{random.randint(100000, 999999)}"
            exp = (dt.now(tz=timezone.utc) + timedelta(minutes=15)).isoformat()
            db.setUserVerification(user.id, code, exp)
            try:
                # Send verification email and always print to console
                send_verification_email(user.email, code, name=getattr(user, "displayName", None))
            except Exception as mail_err:
                logger.warning(f"Failed to send verification email on login: {mail_err}")
            # Inform client to present verification dialog
            detail = {"code": "email_not_confirmed", "status": "verification_required", "message": "Email not verified. Verification code resent."}
            if _debug_enabled():
                detail["debug"] = {"verificationCode": code}
            raise HTTPException(status_code=403, detail=detail)
        if not user.pw_hash:
            detail = _error_payload(
                code="invalid_credentials",
                message="Invalid email or password",
                field=None,
                extra={"why": "password_not_set", "userId": user.id},
            )
            raise HTTPException(status_code=401, detail=detail)

        # Lockout check
        from datetime import datetime, timezone, timedelta
        now = datetime.now(tz=timezone.utc)
        # If user is currently locked out
        if user.lockout_until:
            try:
                lock_dt = datetime.fromisoformat(user.lockout_until)
                if lock_dt.tzinfo is None:
                    lock_dt = lock_dt.replace(tzinfo=timezone.utc)
            except Exception:
                lock_dt = now
            if lock_dt > now:
                remaining = int((lock_dt - now).total_seconds() // 60) or 1
                raise HTTPException(status_code=403, detail=f"account_locked_{remaining}_minutes")

        # Verify password
        if not verify_password(password, user.pw_hash):
            attempts = int(user.failed_login_attempts or 0) + 1
            max_attempts = int(settings.MAX_LOGIN_ATTEMPTS)
            if attempts >= max_attempts:
                lock_minutes = int(settings.LOCKOUT_DURATION_MINS)
                lock_until = (now + timedelta(minutes=lock_minutes)).isoformat()
                db.setUserLockout(user.id, attempts, lock_until)
                raise HTTPException(status_code=403, detail=f"account_locked_{lock_minutes}_minutes")
            else:
                db.setUserLockout(user.id, attempts, None)
                raise HTTPException(status_code=400, detail="login_invalid_password_error")

        # Success: reset counters and set last_login
        db.setUserLoginSuccess(user.id, now.isoformat())

        token = create_jwt({"sub": user.id, "tenant": user.tenantId, "email": user.email})
        refresh = create_refresh_jwt({"sub": user.id, "tenant": user.tenantId})
        _set_refresh_cookie(response, refresh)
        # Align with identity_service TokenData by returning only access_token
        return TokenData(access_token=token)
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"/login error: {e}\n{tb}")
        detail = {"code": "internal_error", "message": "Failed to log in"}
        if _debug_enabled():
            detail["debug"] = str(e)
            detail["trace"] = tb
        raise HTTPException(status_code=500, detail=detail)


@router.get("/me")
def me(req: Request):
    auth = req.headers.get("authorization") or ""
    token = auth.split(" ")[-1] if auth.lower().startswith("bearer ") else None
    payload = decode_jwt(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="unauthorized")
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant")
    # Return full user info including displayName when available
    user = db.getUserById(str(user_id)) if user_id else None
    display_name = getattr(user, "displayName", None) if user else None
    email = getattr(user, "email", None) if user else (payload.get("email") if payload else None)
    return {"id": user_id, "email": email, "displayName": display_name, "tenantId": tenant_id}


class UpdateMeBody(BaseModel):
    displayName: str | None = Field(default=None, min_length=1, max_length=100)
    # Support identity_service-style fields as a fallback
    first_name: str | None = Field(default=None, min_length=1, max_length=50)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    # Email updates disabled in UI; accept but do not change
    email: EmailStr | None = None


@router.patch("/me", summary="Update current user profile", tags=["auth", "profile"])
def update_me(req: Request, body: UpdateMeBody):
    auth = req.headers.get("authorization") or ""
    token = auth.split(" ")[-1] if auth.lower().startswith("bearer ") else None
    payload = decode_jwt(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="unauthorized")
    user_id = str(payload.get("sub") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="unauthorized")

    # Normalize to displayName if only first/last provided
    if (body.displayName is None) and (body.first_name or body.last_name):
        parts: list[str] = []
        if body.first_name:
            parts.append((body.first_name or "").strip())
        if body.last_name:
            parts.append((body.last_name or "").strip())
        name_combined = " ".join([p for p in parts if p]).strip()
        if name_combined:
            body.displayName = name_combined

    # Handle displayName update
    updated_user = None
    if body.displayName is not None:
        display = (body.displayName or "").strip()
        if not display:
            raise HTTPException(status_code=422, detail=_error_payload(
                code="invalid_display_name", message="Display name is required", field="displayName"
            ))
        try:
            updated_user = db.updateUserDisplayName(user_id, display)
        except Exception as e:
            raise HTTPException(status_code=500, detail=_error_payload(
                code="update_failed", message="Could not update profile", extra={"error": str(e)} if _debug_enabled() else None
            ))

    # Email change not supported in this service
    if body.email is not None:
        # If they attempted to change email, reject; if it matches, ignore
        current = db.getUserById(user_id)
        if current and current.email and str(body.email).lower() != str(current.email).lower():
            raise HTTPException(status_code=400, detail=_error_payload(
                code="email_change_not_supported", message="Email changes are not supported"
            ))

    final = updated_user or db.getUserById(user_id)
    if not final:
        raise HTTPException(status_code=404, detail=_error_payload(code="user_not_found", message="User not found"))
    return {"id": final.id, "email": final.email, "displayName": final.displayName, "tenantId": final.tenantId}


class ChangePasswordBody(BaseModel):
    oldPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=8, max_length=200)
    confirmPassword: str = Field(min_length=8, max_length=200)


def _require_auth(req: Request) -> tuple[str, str]:
    auth = req.headers.get("authorization") or ""
    token = auth.split(" ")[-1] if auth.lower().startswith("bearer ") else None
    payload = decode_jwt(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="unauthorized")
    user_id = str(payload.get("sub") or "")
    tenant_id = str(payload.get("tenant") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail="unauthorized")
    return user_id, tenant_id


def _change_password(req: Request, body: ChangePasswordBody):
    user_id, tenant_id = _require_auth(req)

    # Validate new password and confirmation
    if body.newPassword != body.confirmPassword:
        raise HTTPException(status_code=422, detail=_error_payload(
            code="passwords_do_not_match", message="New password and confirmation do not match", field="confirmPassword"
        ))
    issues = _password_issues(body.newPassword)
    if issues:
        raise HTTPException(status_code=422, detail=_error_payload(
            code="weak_password", message="Password does not meet requirements", field="newPassword",
            extra={"issues": issues}
        ))

    user = db.getUserById(user_id)
    if not user or not user.pw_hash:
        # If no existing hash, we cannot change password in this service
        raise HTTPException(status_code=400, detail=_error_payload(
            code="password_change_not_supported", message="Password change not available for this account"
        ))

    if not verify_password(body.oldPassword, user.pw_hash):
        raise HTTPException(status_code=400, detail=_error_payload(
            code="old_password_incorrect", message="Old password is incorrect", field="oldPassword"
        ))

    new_hash = hash_password(body.newPassword)
    # Store in single hash field; salt/iters unused for passlib hashes
    try:
        db.updateUserPassword(user_id, "", new_hash, 0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=_error_payload(
            code="update_failed", message="Could not change password"
        ))
    return {"ok": True, "message": "Password changed successfully"}


@router.put("/me/change-password", summary="Change password (PUT)", tags=["auth", "profile"])
def change_password_put(req: Request, body: ChangePasswordBody):
    return _change_password(req, body)


@router.post("/me/change-password", summary="Change password (POST)", tags=["auth", "profile"])
def change_password_post(req: Request, body: ChangePasswordBody):
    return _change_password(req, body)


# Accept PUT as an alias for updating the current user
@router.put("/me", summary="Update current user profile (PUT)", tags=["auth", "profile"])
def put_update_me(req: Request, body: UpdateMeBody):
    return update_me(req, body)

# Accept POST as an additional alias for environments that block PATCH/PUT
@router.post("/me", summary="Update current user profile (POST)", tags=["auth", "profile"])
def post_update_me(req: Request, body: UpdateMeBody):
    return update_me(req, body)


# Optional: Identity-service style path under this router (will be /api/auth/me/edit-profile)
@router.put("/me/edit-profile", summary="Edit profile (identity-service style)", tags=["auth", "profile"])
def edit_profile_alias(req: Request, body: UpdateMeBody):
    return update_me(req, body)

# Accept POST as an alias for edit-profile to avoid 404s on environments preferring POST
@router.post("/me/edit-profile", summary="Edit profile (POST alias)", tags=["auth", "profile"])
def edit_profile_alias_post(req: Request, body: UpdateMeBody):
    return update_me(req, body)


@router.post("/refresh")
def refresh(req: Request):
    refresh_token = req.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=403, detail="no_refresh_token")
    payload = decode_refresh_jwt(refresh_token)
    if not payload:
        raise HTTPException(status_code=403, detail="invalid_refresh_token")
    sub = payload.get("sub")
    tenant = payload.get("tenant")
    if not sub or not tenant:
        raise HTTPException(status_code=403, detail="invalid_refresh_token")
    # Mint a new access token and rotate refresh token
    token = create_jwt({"sub": sub, "tenant": tenant})
    new_refresh = create_refresh_jwt({"sub": sub, "tenant": tenant})
    resp = Response()
    _set_refresh_cookie(resp, new_refresh)
    resp.media_type = "application/json"
    # Align response shape to identity_service: { "access_token": "..." }
    resp.body = ("{" f"\"access_token\": \"{token}\"" "}").encode("utf-8")
    return resp


@router.post("/logout")
def logout():
    resp = Response()
    resp.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    resp.media_type = "application/json"
    resp.body = b'{"ok": true}'
    return resp


# New: Align to identity_service registration endpoint name and response shape
@router.post("/account")
def register_account(req: Request, body: UserCreate):
    try:
        tenant_id = req.headers.get("x-tenant-id") or "dev-tenant"
        tenant = db.upsertTenant(tenant_id, tenant_id)
        # recaptcha validation similar to identity_service (verified in service layer there)
        verify_recaptcha(getattr(body, "recaptcha_token", None))
        email = _normalize_email(str(body.email))
        # Basic field validation
        fn = (body.first_name or "").strip()
        ln = (body.last_name or "").strip()
        if not fn or not ln:
            raise HTTPException(status_code=422, detail=_error_payload(
                code="invalid_name", message="First and last name are required"
            ))
        # Enforce password quality
        issues = _password_issues(body.password)
        if issues:
            raise HTTPException(
                status_code=422,
                detail=_error_payload(
                    code="weak_password",
                    message="Password does not meet requirements",
                    field="password",
                    extra={"issues": issues},
                ),
            )
        # Build display name from first/last name
        display_name = (fn + " " + ln).strip() or email.split("@")[0]
        existing = db.getUserByEmail(tenant.id, email)
        if existing:
            # identity_service returns 400 on existing email
            raise HTTPException(status_code=400, detail=_error_payload(
                code="email_taken", message="Email already registered", field="email"
            ))

        pwd_hash = hash_password(body.password)
        user = db.createUserWithAuthEmail(tenant.id, email, display_name or email.split("@")[0], "", pwd_hash, 0)

        # Send verification code (debug only surfaces code)
        import random
        from datetime import timedelta, timezone, datetime as dt
        code = f"{random.randint(100000, 999999)}"
        exp = (dt.now(tz=timezone.utc) + timedelta(minutes=15)).isoformat()
        db.setUserVerification(user.id, code, exp)

        payload = {
            "id": user.id,
            "email": user.email,
            "displayName": user.displayName,
            "tenantId": user.tenantId,
            "email_confirmed": False,
        }
        if _debug_enabled():
            payload["debug"] = {"verificationCode": code}
        return JSONResponse(status_code=status.HTTP_201_CREATED, content=payload)
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"/account error: {e}\n{tb}")
        detail = {"code": "internal_error", "message": "Failed to create account"}
        if _debug_enabled():
            detail["debug"] = str(e)
            detail["trace"] = tb
        raise HTTPException(status_code=500, detail=detail)


# New: Align to identity_service revoke route (requires auth)
@router.post("/revoke")
def revoke(req: Request):
    auth = req.headers.get("authorization") or ""
    token = auth.split(" ")[-1] if auth.lower().startswith("bearer ") else None
    payload = decode_jwt(token) if token else None
    if not payload:
        raise HTTPException(status_code=401, detail="unauthorized")
    resp = Response()
    # Delete refresh cookie similar to logout, but keep semantics distinct
    resp.delete_cookie(REFRESH_COOKIE_NAME, path="/")
    resp.media_type = "application/json"
    resp.body = b'{}'
    return resp


# New: Stub for social login parity
@router.post("/social-login")
def social_login_stub():
    raise HTTPException(status_code=501, detail="social_login_not_implemented")


@router.post("/verify-registration")
def verify_registration(req: Request, body: RegistrationConfirmation):
    from datetime import datetime as dt, timezone
    tenant_id = req.headers.get("x-tenant-id") or "dev-tenant"
    tenant = db.upsertTenant(tenant_id, tenant_id)
    # Do not log email or verification code
    user = db.getUserByEmail(tenant.id, str(body.email))
    if not user:
        raise HTTPException(status_code=404, detail=_error_payload(
            code="user_not_found",
            message="No user found for this email",
            field="email",
        ))
    # recaptcha validation aligns with identity_service confirm flow
    verify_recaptcha(getattr(body, "recaptcha_token", None))
    if user.email_confirmed:
        return JSONResponse(status_code=200, content={"ok": True, "message": "Email already confirmed"})
    # Check code/expiry
    if not user.verification_code or user.verification_code != body.verificationCode:
        raise HTTPException(status_code=400, detail=_error_payload(
            code="invalid_verification_code",
            message="The code you entered is incorrect",
            field="verificationCode",
        ))
    try:
        exp_dt = dt.fromisoformat(user.verification_code_exp) if user.verification_code_exp else None
        if exp_dt and exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
    except Exception:
        exp_dt = None
    if exp_dt and exp_dt < dt.now(tz=timezone.utc):
        raise HTTPException(status_code=400, detail=_error_payload(
            code="expired_verification_code",
            message="The verification code has expired. Please request a new code",
        ))
    db.confirmUserEmail(user.id)
    return JSONResponse(status_code=202, content={"ok": True, "message": "Email verified. You can now log in."})


@router.post("/send-code")
def send_verification_code(req: Request, body: EmailData):
    # Resend verification code for unconfirmed users
    from datetime import timedelta, timezone, datetime as dt
    tenant_id = req.headers.get("x-tenant-id") or "dev-tenant"
    tenant = db.upsertTenant(tenant_id, tenant_id)
    # Do not log email
    user = db.getUserByEmail(tenant.id, str(body.email))
    if not user:
        raise HTTPException(status_code=404, detail=_error_payload(
            code="user_not_found",
            message="No user found for this email",
            field="email",
        ))
    # recaptcha validation (identity_service requires it)
    verify_recaptcha(getattr(body, "recaptcha_token", None))
    if user.email_confirmed:
        return JSONResponse(status_code=200, content={"ok": True, "message": "Email already confirmed"})
    import random
    code = f"{random.randint(100000, 999999)}"
    exp = (dt.now(tz=timezone.utc) + timedelta(minutes=15)).isoformat()
    db.setUserVerification(user.id, code, exp)

    # Send the code via email; always log to console and try provider
    try:
        send_verification_email(user.email, code, name=getattr(user, "displayName", None))
    except Exception as mail_err:
        logger.warning(f"Failed to resend verification email: {mail_err}")

    detail = {"ok": True, "status": "verification_sent"}
    if _debug_enabled():
        detail["debug"] = {"verificationCode": code}
    return JSONResponse(status_code=200, content=detail)


# Forgot password: request reset link
@router.post("/forgot-password")
def forgot_password(req: Request, body: ForgotPasswordBody):
    tenant_id = req.headers.get("x-tenant-id") or "dev-tenant"
    tenant = db.upsertTenant(tenant_id, tenant_id)
    # Validate recaptcha if enabled
    verify_recaptcha(getattr(body, "recaptcha_token", None))
    # Normalize email and attempt lookup; do not reveal existence
    email = _normalize_email(str(body.email))
    user = db.getUserByEmail(tenant.id, email)
    if user:
        # Create short-lived reset token and link
        token = create_password_reset_token(email, minutes=15)
        # Build link target, prefer the requesting Origin when available so the link lands on the same frontend
        import os, urllib.parse
        origin = req.headers.get("origin") or ""
        if origin and re.match(r"^https?://", origin):
            base = origin.rstrip("/") + "/reset-password"
        else:
            base = os.getenv("RESET_PASSWORD_URL") or getattr(settings, "RESET_PASSWORD_URL", None) or "http://localhost:8080/reset-password"
        if "{token}" in base:
            link = base.replace("{token}", urllib.parse.quote(token))
        else:
            sep = "&" if ("?" in base) else "?"
            link = f"{base}{sep}token={urllib.parse.quote(token)}"
        try:
            # Use shared email; template expects a code, but we pass link/token as provided
            send_password_reset_email_shared(email, link, name=getattr(user, "displayName", None))
        except Exception as mail_err:
            logger.warning(f"Failed to send password reset email: {mail_err}")
    # Always respond success to avoid account enumeration
    return JSONResponse(status_code=200, content={"ok": True})


# Reset password: consume token and set new password
@router.post("/reset-password")
def reset_password(req: Request, body: ResetPasswordBody):
    # Validate token
    payload = decode_password_reset_token(body.token)
    if not payload or not payload.get("email"):
        raise HTTPException(status_code=400, detail=_error_payload(code="invalid_token", message="Reset link is invalid or expired"))
    # Validate new password strength
    issues = _password_issues(body.new_password)
    if issues:
        raise HTTPException(status_code=422, detail=_error_payload(code="weak_password", message="Password does not meet requirements", field="new_password", extra={"issues": issues}))
    email = _normalize_email(str(payload["email"]))
    tenant_id = req.headers.get("x-tenant-id") or "dev-tenant"
    tenant = db.upsertTenant(tenant_id, tenant_id)
    user = db.getUserByEmail(tenant.id, email)
    if not user:
        # Treat as invalid token to avoid leaking account status
        raise HTTPException(status_code=400, detail=_error_payload(code="invalid_token", message="Reset link is invalid or expired"))
    # Update password
    pwd_hash = hash_password(body.new_password)
    db.updateUserPassword(user.id, "", pwd_hash, 0)
    return JSONResponse(status_code=200, content={"ok": True, "message": "Password has been reset. You can now log in."})


# Resend password reset link using token (extract email from token claims even if expired)
@router.post("/resend-reset")
def resend_reset(req: Request, body: ResendResetBody):
    token_in = (body.token or "").strip()
    email = None
    try:
        from jose import jwt
        claims = jwt.get_unverified_claims(token_in)  # type: ignore[attr-defined]
        if isinstance(claims, dict):
            email = claims.get("email")
    except Exception:
        email = None
    # Fallback: try normal decode if not obtained
    if not email:
        payload = decode_password_reset_token(token_in)
        if payload:
            email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail=_error_payload(code="invalid_token", message="Reset link is invalid or expired"))
    # Normalize and send
    email = _normalize_email(str(email))
    tenant_id = req.headers.get("x-tenant-id") or "dev-tenant"
    tenant = db.upsertTenant(tenant_id, tenant_id)
    user = db.getUserByEmail(tenant.id, email)
    if user:
        # Create a new token and send link (reuse origin-based logic)
        new_token = create_password_reset_token(email, minutes=15)
        import urllib.parse
        origin = req.headers.get("origin") or ""
        if origin and re.match(r"^https?://", origin):
            base = origin.rstrip("/") + "/reset-password"
        else:
            base = os.getenv("RESET_PASSWORD_URL") or getattr(settings, "RESET_PASSWORD_URL", None) or "http://localhost:8080/reset-password"
        if "{token}" in base:
            link = base.replace("{token}", urllib.parse.quote(new_token))
        else:
            sep = "&" if ("?" in base) else "?"
            link = f"{base}{sep}token={urllib.parse.quote(new_token)}"
        try:
            send_password_reset_email_shared(email, link, name=getattr(user, "displayName", None))
        except Exception as mail_err:
            logger.warning(f"Failed to send password reset email (resend): {mail_err}")
    # Always 200 OK to avoid account enumeration
    return JSONResponse(status_code=200, content={"ok": True})
