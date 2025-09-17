from __future__ import annotations

import os
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Support running either as a module (python -m app.main / uvicorn app.main:app)
# or directly as a script (python pyserver/app/main.py) without import errors.
try:
    from .db import db
    from .routes.agents import router as agents_router
    from .routes.threads import router as threads_router
    from .routes.chat import router as chat_router
    from .routes.pages import router as pages_router
    from .routes.auth import router as auth_router
    from .routes.auth import UpdateMeBody, update_me as update_me_impl
    from .routes.auth import ChangePasswordBody, change_password_put as change_password_impl
except ImportError:
    # Fallback to absolute imports if relative imports fail (e.g., when run as a script)
    from .db import db
    from routes.agents import router as agents_router
    from .routes.threads import router as threads_router
    from .routes.chat import router as chat_router
    from .routes.pages import router as pages_router
    from .routes.auth import router as auth_router
    from .routes.auth import UpdateMeBody, update_me as update_me_impl
    from .routes.auth import ChangePasswordBody, change_password_put as change_password_impl


app = FastAPI(title="Future-Compass API (FastAPI)")


# Health route (no auth)
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def root():
    return {"message": "Future-Compass API is running", "health": "/health"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    # Return no content to satisfy browser favicon requests without errors
    return Response(status_code=204)


"""
IMPORTANT: Middleware order matters.
We add CORSMiddleware AFTER SimpleAuthMiddleware so it wraps everything
and ensures CORS headers are present even on early returns (e.g., 401).
"""


class SimpleAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Always let CORS preflight through so CORSMiddleware can respond
        if request.method == "OPTIONS":
            return await call_next(request)
        # Public paths (no auth). Support prefixes for docs assets.
        path = request.url.path
        public_exact = {
            "/", "/health", "/openapi.json", "/favicon.ico",
            "/api/auth/login", "/api/auth/signup", "/api/auth/refresh", "/api/auth/logout",
            "/api/auth/account", "/api/auth/verify-registration", "/api/auth/send-code",
        }
        public_prefixes = ("/docs", "/redoc")
        if path in public_exact or any(path.startswith(p) for p in public_prefixes):
            return await call_next(request)

        # Try JWT first
        from .services.auth import decode_jwt  # lazy import
        auth = request.headers.get("authorization") or ""
        token = auth.split(" ")[-1] if auth.lower().startswith("bearer ") else None
        payload = decode_jwt(token) if token else None
        # Default to allowing a dev fallback unless explicitly disabled.
        # Set ALLOW_DEV_FALLBACK=0 in production to enforce auth.
        allow_dev = os.getenv("ALLOW_DEV_FALLBACK", "1") == "1"
        tenant_id = None
        user_id = None
        user_name = None
        if payload:
            tenant_id = payload.get("tenant") or request.headers.get("x-tenant-id") or "dev-tenant"
            user_id = payload.get("sub") or request.headers.get("x-user-id") or "dev-user"
            user_name = request.headers.get("x-user-name") or (payload.get("email") or "User")
        else:
            # Fallback: tenant API key header (x-tenant-key)
            try:
                from .services.tenant_keys import verify_tenant_key
                provided_key = request.headers.get("x-tenant-key") or request.headers.get("X-Tenant-Key")
                if provided_key:
                    tid = verify_tenant_key(provided_key)
                    if tid:
                        tenant_id = tid
                        # For key-based access, allow caller to pass an optional user id/name for scoping
                        user_id = request.headers.get("x-user-id") or "tenant-key-user"
                        user_name = request.headers.get("x-user-name") or "Tenant Key User"
            except Exception:
                # If verification path fails hard, continue to dev or 401 paths below
                pass

            if tenant_id is None:
                if allow_dev:
                    tenant_id = request.headers.get("x-tenant-id") or "dev-tenant"
                    user_id = request.headers.get("x-user-id") or "dev-user"
                    user_name = request.headers.get("x-user-name") or "Dev User"
                else:
                    return JSONResponse(status_code=401, content={"detail": "unauthorized"})

        # ensure entities exist
        db.upsertTenant(tenant_id, tenant_id)
        # Ensure authenticated or key-based user exists (avoid creating dev user twice)
        if payload or (request.headers.get("x-tenant-key") is not None):
            db.upsertUser(tenant_id, user_name, user_id)

        request.state.tenant_id = tenant_id
        request.state.user_id = user_id

        # Seed default agent if none exists
        if not db.listAgents(tenant_id):
            db.createAgent(
                tenant_id,
                {
                    "name": "Future-Compass Advisor",
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "systemPrompt": (
                        "You are Future-Compass, a warm, practical academic guidance assistant. "
                        "Your goal is to help the student decide what to study based on THEIR inputs. "
                        "Conversation style: Ask one clear follow-up question at a time when needed, wait for the reply, and build a plan iteratively. "
                        "When giving guidance, tailor it to the student’s interests, constraints (time, budget, location), and prior experience. "
                        "Keep responses concise (6–10 sentences), specific, and free of generic lists. "
                        "Prefer step-by-step next actions (try course X, do a 7–10 day mini-project Y, reflect on Z) and end with a relevant question."
                    ),
                    "temperature": 0.7,
                },
            )

        return await call_next(request)


app.add_middleware(SimpleAuthMiddleware)


# CORS (allow localhost:8080 and :4000 with credentials, all methods/headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:4000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(agents_router)
app.include_router(threads_router)
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(pages_router)


# Root-level alias to support clients calling identity service style endpoint
@app.put("/me/edit-profile", tags=["auth", "profile"], summary="Root alias: Edit profile (PUT)")
def edit_profile_root(req: Request, body: UpdateMeBody):
    # Reuse the same implementation as /api/auth/me (PATCH/PUT)
    return update_me_impl(req, body)

# Root-level alias to support clients calling /me/change-password
@app.put("/me/change-password", tags=["auth", "profile"], summary="Root alias: Change password (PUT)")
def change_password_root(req: Request, body: ChangePasswordBody):
    return change_password_impl(req, body)

# Root-level POST aliases for environments that use POST for updates
@app.post("/me/edit-profile", tags=["auth", "profile"], summary="Root alias: Edit profile (POST)")
def edit_profile_root_post(req: Request, body: UpdateMeBody):
    return update_me_impl(req, body)

@app.post("/me/change-password", tags=["auth", "profile"], summary="Root alias: Change password (POST)")
def change_password_root_post(req: Request, body: ChangePasswordBody):
    return change_password_impl(req, body)


if __name__ == "__main__":
    # Optional convenience for local runs: `python pyserver/app/main.py`
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    # When run as a script, the import path for "app.main:app" may not resolve
    # unless the parent directory is on sys.path. Use the object directly.
    uvicorn.run(app, host=host, port=port, reload=os.getenv("RELOAD", "1") == "1")
