import json
import logging
import os
import secrets
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
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.core.auth import require_auth
from src.modules.admin_ui.service import (
    create_tenant as create_tenant_record,
    delete_document as delete_document_record,
    delete_tenant as delete_tenant_record,
    get_tenant_documents,
    get_tenants,
    rename_tenant as rename_tenant_record,
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


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login", response_class=HTMLResponse)
async def login_action(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    correct_user = os.getenv("ADMIN_USER", "admin")
    correct_pass = os.getenv("ADMIN_PASSWORD", "admin")
    admin_token = os.getenv("ADMIN_TOKEN", "secret-admin-token")

    if secrets.compare_digest(username, correct_user) and secrets.compare_digest(password, correct_pass):
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="session_token", value=admin_token, httponly=True)
        return response

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid username or password"},
        status_code=401,
    )


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_token")
    return response


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(require_auth)):
    tenants = await get_tenants()
    gemini_model = get_gemini_model_name()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tenants": tenants,
            "selected_tenant": None,
            "username": username,
            "gemini_model": gemini_model,
        },
    )


@router.post("/tenants", response_class=HTMLResponse)
async def create_tenant(
    request: Request,
    slug: Annotated[str, Form()],
    username: str = Depends(require_auth),
):
    await create_tenant_record(slug)
    return RedirectResponse(url="/", status_code=303)


@router.get("/tenants/{tenant_id}", response_class=HTMLResponse)
async def view_tenant(
    request: Request,
    tenant_id: int,
    username: str = Depends(require_auth),
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
            "username": username,
            "gemini_model": get_gemini_model_name(),
        },
    )


@router.post("/tenants/{tenant_id}/rename", response_class=HTMLResponse)
async def rename_tenant(
    request: Request,
    tenant_id: int,
    slug: Annotated[str, Form()],
    username: str = Depends(require_auth),
):
    await rename_tenant_record(tenant_id, slug)
    return RedirectResponse(url=f"/tenants/{tenant_id}", status_code=303)


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    request: Request,
    tenant_id: int,
    username: str = Depends(require_auth),
):
    await delete_tenant_record(tenant_id)
    return Response(status_code=200, headers={"HX-Redirect": "/"})


@router.post("/ingest", response_class=HTMLResponse)
async def ingest_file(
    request: Request,
    background_tasks: BackgroundTasks,
    tenant_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    username: str = Depends(require_auth),
):
    if not has_supported_ingest_extension(file.filename):
        supported_formats = ", ".join(SUPPORTED_INGEST_EXTENSIONS)
        return HTMLResponse(f'<div class="text-red-500">Supported formats: {supported_formats}</div>')

    try:
        temp_path = save_upload_to_temp_file(file)
        background_tasks.add_task(
            ingest_document,
            tenant_id,
            file.filename,
            temp_file_path=temp_path,
        )

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
    username: str = Depends(require_auth),
):
    answer = await generate_answer(
        tenant_id,
        query,
        provider=provider,
    )

    full_response_json = json.dumps(
        {
            "answer": answer,
            "requires_human": False,
            "tenant_id": str(tenant_id),
            "query": query,
        },
        indent=2,
    )

    return templates.TemplateResponse(
        "partials/chat_response.html",
        {
            "request": request,
            "answer": answer,
            "query": query,
            "full_response_json": full_response_json,
        },
    )


@router.delete("/documents/{doc_id}", response_class=HTMLResponse)
async def delete_document(
    request: Request,
    doc_id: UUID,
    username: str = Depends(require_auth),
):
    await delete_document_record(doc_id)
    return HTMLResponse("")


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
