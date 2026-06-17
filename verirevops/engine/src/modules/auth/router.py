from typing import Annotated

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.core.security import create_access_token
from src.modules.auth.service import (
    accept_invitation,
    authenticate_user,
    create_tenant_with_admin,
    get_invitation_by_token,
)

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


# ── Registration ──────────────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@router.post("/register", response_class=HTMLResponse)
async def register_action(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    tenant_slug: Annotated[str, Form()],
    full_name: Annotated[str | None, Form()] = None,
):
    try:
        user = await create_tenant_with_admin(email, password, tenant_slug, full_name)
    except Exception as exc:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": str(exc.detail) if hasattr(exc, "detail") else str(exc)},
            status_code=400,
        )

    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role, "tenant_id": user.tenant_id})
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax")
    return response


# ── Login / Logout ────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    invited = request.query_params.get("invited")
    return templates.TemplateResponse("login.html", {"request": request, "invited": invited})


@router.post("/login", response_class=HTMLResponse)
async def login_action(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    user = await authenticate_user(email, password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password"},
            status_code=401,
        )

    token = create_access_token({"sub": str(user.id), "email": user.email, "role": user.role, "tenant_id": user.tenant_id})
    redirect_url = "/" if user.role == "superadmin" else "/dashboard"
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax")
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response


# ── Invitation acceptance ─────────────────────────────────────────────────────

@router.get("/invite/{token}", response_class=HTMLResponse)
async def invite_page(request: Request, token: str):
    invitation = await get_invitation_by_token(token)
    if not invitation:
        return templates.TemplateResponse(
            "invite.html",
            {"request": request, "error": "Invitation not found or already used", "token": token},
        )
    if invitation.accepted_at:
        return templates.TemplateResponse(
            "invite.html",
            {"request": request, "error": "This invitation has already been accepted", "token": token},
        )
    return templates.TemplateResponse(
        "invite.html",
        {"request": request, "invitation": invitation, "token": token},
    )


@router.post("/invite/{token}", response_class=HTMLResponse)
async def invite_action(
    request: Request,
    token: str,
    password: Annotated[str, Form()],
    full_name: Annotated[str | None, Form()] = None,
):
    try:
        await accept_invitation(token, password, full_name)
    except Exception as exc:
        invitation = await get_invitation_by_token(token)
        return templates.TemplateResponse(
            "invite.html",
            {
                "request": request,
                "invitation": invitation,
                "token": token,
                "error": str(exc.detail) if hasattr(exc, "detail") else str(exc),
            },
            status_code=400,
        )

    return RedirectResponse(url="/login?invited=1", status_code=status.HTTP_303_SEE_OTHER)
