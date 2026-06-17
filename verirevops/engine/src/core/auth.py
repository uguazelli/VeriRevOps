import os
import secrets as std_secrets
from fastapi import Depends, HTTPException, Request, status

from src.core.security import decode_token


def _extract_token(request: Request) -> str | None:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
    return token


async def get_current_user(request: Request):
    """Extract and validate the current user from JWT cookie or Bearer header.

    Also supports legacy ADMIN_TOKEN env var for backward-compatible API clients.
    """
    token = _extract_token(request)
    if not token:
        return None

    # Legacy ADMIN_TOKEN: treated as superadmin for backward compat
    admin_token = os.getenv("ADMIN_TOKEN")
    if admin_token and std_secrets.compare_digest(token, admin_token):
        from src.core.models import User
        return User(id=0, email="admin@system", role="superadmin", is_active=True, hashed_password="")

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    from src.modules.auth.service import get_user_by_id
    return await get_user_by_id(int(user_id))


def require_auth(request: Request, user=Depends(get_current_user)):
    """Require any authenticated, active user. Redirects UI to /login, returns 401 for API."""
    if not user or not user.is_active:
        is_api = request.url.path.startswith("/api") or "application/json" in request.headers.get("accept", "")
        if is_api:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"},
        )
    return user


def require_superadmin(user=Depends(require_auth)):
    """Require superadmin role."""
    if user.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return user


def require_tenant_admin(user=Depends(require_auth)):
    """Require tenant_admin or superadmin role."""
    if user.role not in ("superadmin", "tenant_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
