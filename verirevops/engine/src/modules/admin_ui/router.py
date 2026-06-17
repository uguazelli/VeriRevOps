import json
import logging
import os
import shutil
import tempfile
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.core.auth import require_auth, require_superadmin, require_tenant_admin
from src.core.models import User
from src.modules.admin_ui.service import (
    create_tenant as create_tenant_record,
    delete_document as delete_document_record,
    delete_tenant as delete_tenant_record,
    get_tenant_documents,
    get_tenants,
    rename_tenant as rename_tenant_record,
)
from src.modules.auth.service import (
    create_invitation,
    get_tenant_users,
    get_tenant_webhook_token,
)
from src.modules.rag import generate_answer, ingest_document


logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="src/templates")
router = APIRouter()

SUPPORTED_INGEST_EXTENSIONS = (
    ".txt",
    ".md",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".pdf",
    ".docx",
)


# ── Superadmin: all-tenant dashboard ─────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(require_superadmin)):
    tenants = await get_tenants()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tenants": tenants,
            "selected_tenant": None,
            "user": user,
            "gemini_model": get_gemini_model_name(),
        },
    )


@router.post("/tenants", response_class=HTMLResponse)
async def create_tenant(
    request: Request,
    slug: Annotated[str, Form()],
    user: User = Depends(require_superadmin),
):
    await create_tenant_record(slug)
    return RedirectResponse(url="/", status_code=303)


@router.get("/tenants/{tenant_id}", response_class=HTMLResponse)
async def view_tenant(
    request: Request,
    tenant_id: int,
    user: User = Depends(require_superadmin),
):
    tenants = await get_tenants()
    documents = await get_tenant_documents(tenant_id)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tenants": tenants,
            "selected_tenant": {
                "id": tenant_id,
                "slug": get_tenant_slug(tenants, tenant_id),
            },
            "documents": documents,
            "user": user,
            "gemini_model": get_gemini_model_name(),
        },
    )


@router.post("/tenants/{tenant_id}/rename", response_class=HTMLResponse)
async def rename_tenant(
    request: Request,
    tenant_id: int,
    slug: Annotated[str, Form()],
    user: User = Depends(require_superadmin),
):
    await rename_tenant_record(tenant_id, slug)
    return RedirectResponse(url=f"/tenants/{tenant_id}", status_code=303)


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    request: Request,
    tenant_id: int,
    user: User = Depends(require_superadmin),
):
    await delete_tenant_record(tenant_id)
    return Response(status_code=200, headers={"HX-Redirect": "/"})


# ── Tenant user: own-tenant dashboard ────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def tenant_dashboard(request: Request, user: User = Depends(require_auth)):
    if user.role == "superadmin":
        return RedirectResponse(url="/", status_code=303)
    if not user.tenant_id:
        raise HTTPException(status_code=400, detail="No tenant associated with this account")

    documents = await get_tenant_documents(user.tenant_id)
    return templates.TemplateResponse(
        "tenant_dashboard.html",
        {
            "request": request,
            "user": user,
            "documents": documents,
            "gemini_model": get_gemini_model_name(),
        },
    )


# ── Tenant settings + team management ────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: User = Depends(require_tenant_admin)):
    if user.role == "superadmin":
        return RedirectResponse(url="/", status_code=303)

    team = await get_tenant_users(user.tenant_id)
    webhook_token = await get_tenant_webhook_token(user.tenant_id)
    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "team": team,
            "webhook_token": webhook_token,
            "invite_sent": None,
        },
    )


@router.post("/settings/invite", response_class=HTMLResponse)
async def invite_team_member(
    request: Request,
    email: Annotated[str, Form()],
    role: Annotated[str, Form()] = "tenant_member",
    user: User = Depends(require_tenant_admin),
):
    if user.role == "superadmin":
        raise HTTPException(403, "Use the admin panel to manage superadmin users")

    invitation = await create_invitation(
        tenant_id=user.tenant_id,
        email=email,
        role=role,
        created_by_id=user.id,
    )

    invite_url = str(request.base_url).rstrip("/") + f"/invite/{invitation.token}"
    team = await get_tenant_users(user.tenant_id)
    webhook_token = await get_tenant_webhook_token(user.tenant_id)

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "team": team,
            "webhook_token": webhook_token,
            "invite_sent": {"email": email, "url": invite_url},
        },
    )


# ── Shared: document ingest, query, delete ────────────────────────────────────

@router.post("/ingest", response_class=HTMLResponse)
async def ingest_file(
    request: Request,
    background_tasks: BackgroundTasks,
    tenant_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    user: User = Depends(require_auth),
):
    # Tenant users can only ingest into their own tenant
    if user.role != "superadmin" and user.tenant_id != tenant_id:
        return HTMLResponse('<div class="text-red-500">Access denied to this tenant</div>', status_code=403)

    if not has_supported_ingest_extension(file.filename):
        supported_formats = ", ".join(SUPPORTED_INGEST_EXTENSIONS)
        return HTMLResponse(f'<div class="text-red-500">Supported formats: {supported_formats}</div>')

    try:
        temp_path = save_upload_to_temp_file(file)
        background_tasks.add_task(ingest_document, tenant_id, file.filename, temp_file_path=temp_path)
        return HTMLResponse(
            f'<div class="text-green-500 mb-2">Processing {file.filename}... refreshing page.</div>'
            f'<script>setTimeout(() => window.location.reload(), 1500);</script>'
        )
    except Exception as exc:
        logger.error("Error reading file: %s", exc)
        return HTMLResponse('<div class="text-red-500">Error reading file</div>')


@router.post("/query", response_class=HTMLResponse)
async def query_rag(
    request: Request,
    tenant_id: Annotated[int, Form()],
    query: Annotated[str, Form()],
    provider: Annotated[str, Form()] = "gemini",
    user: User = Depends(require_auth),
):
    if user.role != "superadmin" and user.tenant_id != tenant_id:
        return HTMLResponse('<div class="text-red-500">Access denied to this tenant</div>', status_code=403)

    answer = await generate_answer(tenant_id, query, provider=provider)
    full_response_json = json.dumps(
        {"answer": answer, "requires_human": False, "tenant_id": str(tenant_id), "query": query},
        indent=2,
    )
    return templates.TemplateResponse(
        "partials/chat_response.html",
        {"request": request, "answer": answer, "query": query, "full_response_json": full_response_json},
    )


@router.delete("/documents/{doc_id}", response_class=HTMLResponse)
async def delete_document(
    request: Request,
    doc_id: UUID,
    user: User = Depends(require_auth),
):
    await delete_document_record(doc_id)
    return HTMLResponse("")


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_gemini_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "gemini-2.0-flash").replace("models/", "")


def get_tenant_slug(tenants, tenant_id: int) -> str:
    for current_tenant_id, tenant_slug in tenants:
        if str(current_tenant_id) == str(tenant_id):
            return tenant_slug
    return "Unknown"


def has_supported_ingest_extension(filename: str) -> bool:
    return filename.lower().endswith(SUPPORTED_INGEST_EXTENSIONS)


def save_upload_to_temp_file(file: UploadFile) -> str:
    ext = os.path.splitext(file.filename)[1]
    fd, temp_path = tempfile.mkstemp(suffix=ext)
    with os.fdopen(fd, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return temp_path
