"""/auth endpoints — login, me, logout."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from loguru import logger
from pydantic import BaseModel

from app.auth import (
    AuthContext, TokenResponse,
    authenticate, current_user, issue_token, update_last_login,
    PERMISSIONS,
)

router = APIRouter()


class LoginJSONRequest(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=TokenResponse)
async def login_form(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """OAuth2-style login (form-encoded). Used by Swagger UI's 'Authorize' button."""
    return await _do_login(form.username, form.password)


@router.post("/login-json", response_model=TokenResponse)
async def login_json(req: LoginJSONRequest) -> TokenResponse:
    """JSON login — convenient for the React frontend."""
    return await _do_login(req.username, req.password)


async def _do_login(username: str, password: str) -> TokenResponse:
    ctx = await authenticate(username, password)
    if not ctx:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid username or password",
        )
    await update_last_login(ctx.user_id)
    token = issue_token(ctx)
    logger.info(f"login user={ctx.user_id} role={ctx.role} school={ctx.school_id}")
    return TokenResponse(
        access_token=token,
        expires_in=8 * 60 * 60,
        user={
            "user_id": ctx.user_id,
            "school_id": ctx.school_id,
            "role": ctx.role,
            "linked_id": ctx.linked_id,
            "full_name": ctx.full_name,
            "email": ctx.email,
        },
    )


@router.get("/me")
async def me(ctx: AuthContext = Depends(current_user)) -> dict:
    """Return the current user's identity + their effective permissions."""
    return {
        "user_id": ctx.user_id,
        "school_id": ctx.school_id,
        "role": ctx.role,
        "linked_id": ctx.linked_id,
        "full_name": ctx.full_name,
        "email": ctx.email,
        "permissions": sorted(PERMISSIONS.get(ctx.role, set())),
    }


@router.post("/logout")
async def logout(ctx: AuthContext = Depends(current_user)) -> dict:
    """
    Token-based logout. Since we use stateless JWTs, the client just
    discards the token. (For revocation, implement a denylist in Redis.)
    """
    logger.info(f"logout user={ctx.user_id}")
    return {"ok": True, "message": "Logged out"}
