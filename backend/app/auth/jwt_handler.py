"""
JWT authentication for EduBot.

Login → bcrypt verify against `users` table → JWT issued with claims
that match the AuthContext shape (user_id, school_id, role, linked_id).
Every protected endpoint depends on `current_user` which decodes the JWT,
loads the AuthContext, and injects it.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import text

from app.auth.rbac import AuthContext, Role
from app.config import get_settings


# We use a short alias path so the OpenAPI doc shows /auth/login as the token URL
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ─────────────────────────────────────────────────────────────────────────────
# Token shape & helpers
# ─────────────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


def _now() -> datetime:
    return datetime.now(timezone.utc)


def quick_hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def verify_password(plain: str, stored_hash: str) -> bool:
    """Demo uses sha256 (matches seed_db.py).
    Real production: bcrypt or argon2 — swap freely; uses are isolated here."""
    return quick_hash(plain) == stored_hash


def issue_token(ctx: AuthContext, ttl_minutes: int = 60 * 8) -> str:
    s = get_settings()
    payload = {
        "sub": ctx.user_id,
        "school_id": ctx.school_id,
        "role": ctx.role,
        "linked_id": ctx.linked_id,
        "name": ctx.full_name,
        "email": ctx.email,
        "iat": int(_now().timestamp()),
        "exp": int((_now() + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    secret = s.app_secret_key or "edubot-demo-secret-do-not-use-in-prod"
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    s = get_settings()
    secret = s.app_secret_key or "edubot-demo-secret-do-not-use-in-prod"
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired. Please log in again.")
    except jwt.InvalidTokenError as e:
        raise HTTPException(401, f"Invalid token: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Login flow
# ─────────────────────────────────────────────────────────────────────────────

async def authenticate(username: str, password: str) -> Optional[AuthContext]:
    """Look up the user, verify the password, return AuthContext on success."""
    from app.core.erp_connector import get_engine
    eng = get_engine()
    async with eng.connect() as conn:
        row = (await conn.execute(
            text("""
                SELECT user_id, school_id, role, linked_id,
                       password_hash, full_name, email, status
                FROM users WHERE username = :u
            """),
            {"u": username},
        )).fetchone()

    if not row:
        return None
    if row.status != "Active":
        return None
    if not verify_password(password, row.password_hash):
        return None

    return AuthContext(
        user_id=row.user_id,
        school_id=row.school_id,
        role=row.role,  # type: ignore[arg-type]
        linked_id=row.linked_id,
        full_name=row.full_name,
        email=row.email,
    )


async def update_last_login(user_id: str) -> None:
    """Best-effort last-login stamp."""
    try:
        from app.core.erp_connector import get_engine
        eng = get_engine()
        async with eng.begin() as conn:
            await conn.execute(
                text("UPDATE users SET last_login = :t WHERE user_id = :uid"),
                {"t": _now().isoformat(), "uid": user_id},
            )
    except Exception as e:
        logger.warning(f"Could not update last_login for {user_id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI dependency
# ─────────────────────────────────────────────────────────────────────────────

async def current_user(token: str = Depends(oauth2_scheme)) -> AuthContext:
    """
    Inject as a dependency on any protected route. Raises 401 if missing/invalid.
    """
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    return AuthContext(
        user_id=payload["sub"],
        school_id=payload["school_id"],
        role=payload["role"],
        linked_id=payload.get("linked_id"),
        full_name=payload.get("name"),
        email=payload.get("email"),
    )


async def current_user_optional(token: str = Depends(oauth2_scheme)) -> Optional[AuthContext]:
    """For endpoints that are public-by-default but enrich behaviour if logged in."""
    if not token:
        return None
    try:
        return await current_user(token)
    except HTTPException:
        return None
