import os
import secrets
from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import APIKeyCookie

security = APIKeyCookie(name="session_token", auto_error=False)

def get_current_username(request: Request):
    # Check cookie first
    token = request.cookies.get("session_token")

    # Check Authorization header if no cookie
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        # Redirect logic handled in web routes or return None
        return None

    # Simple token validation (In real app, use better session management)
    # Here we just check if the token matches a secret "admin_token"
    # For simplicity in this "no logic" refactor, we just check a static token
    correct_token = os.getenv("ADMIN_TOKEN")

    if not secrets.compare_digest(token, correct_token):
        return None

    return "admin"

def require_auth(request: Request, username: Annotated[Optional[str], Depends(get_current_username)]):
    if not username:
        # Check if it's an API request or expects JSON
        if request.url.path.startswith("/api") or "application/json" in request.headers.get("accept", "").lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated. Provide 'session_token' cookie or 'Authorization: Bearer <token>' header."
            )

        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"},
        )
    return username
