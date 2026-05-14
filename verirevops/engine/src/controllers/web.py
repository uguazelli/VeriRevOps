import logging
import os
import secrets
import json
import tempfile
import shutil
from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, Request, Depends, UploadFile, File, Form, BackgroundTasks, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.core.db import get_session
from src.core.models import Tenant, Document
from sqlalchemy import select, update, delete
from src.core.auth import require_auth
from src.services.rag import ingest_document, generate_answer

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="src/templates")
router = APIRouter()

# Helpers
async def get_tenants():
    async with get_session() as session:
        tenants = (await session.execute(select(Tenant).order_by(Tenant.created_at.desc()))).scalars().all()
        return [(t.id, t.slug) for t in tenants]

async def get_tenant_documents(tenant_id: int):
    async with get_session() as session:
        docs = (await session.execute(
            select(Document)
            .where(Document.tenant_id == tenant_id)
            .where(Document.parent_id.is_(None))
            .order_by(Document.created_at.desc())
        )).scalars().all()
        return [(d.id, d.filename, d.created_at) for d in docs]

# Login Routes
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
async def login_action(request: Request, username: Annotated[str, Form()], password: Annotated[str, Form()]):
    correct_user = os.getenv("ADMIN_USER", "admin")
    correct_pass = os.getenv("ADMIN_PASSWORD", "admin")

    # We use a static token secret for simplicity
    admin_token = os.getenv("ADMIN_TOKEN", "secret-admin-token")

    if secrets.compare_digest(username, correct_user) and secrets.compare_digest(password, correct_pass):
        response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="session_token", value=admin_token, httponly=True)
        return response

    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"}, status_code=401)

@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_token")
    return response

# Routes
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, username: str = Depends(require_auth)):
    tenants = await get_tenants()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").replace("models/", "")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "tenants": tenants, "selected_tenant": None, "username": username, "gemini_model": gemini_model}
    )

@router.post("/tenants", response_class=HTMLResponse)
async def create_tenant(request: Request, slug: Annotated[str, Form()], username: str = Depends(require_auth)):
    async with get_session() as session:
        session.add(Tenant(slug=slug))
        await session.commit()
    return RedirectResponse(url="/", status_code=303)

@router.get("/tenants/{tenant_id}", response_class=HTMLResponse)
async def view_tenant(request: Request, tenant_id: int, username: str = Depends(require_auth)):
    tenants = await get_tenants()
    documents = await get_tenant_documents(tenant_id)
    tenant_slug = "Unknown"
    for t_id, t_slug in tenants:
        if str(t_id) == str(tenant_id):
            tenant_slug = t_slug
            break

    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").replace("models/", "")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tenants": tenants,
            "selected_tenant": {"id": tenant_id, "slug": tenant_slug},
            "documents": documents,
            "username": username,
            "gemini_model": gemini_model
        }
    )

@router.post("/tenants/{tenant_id}/rename", response_class=HTMLResponse)
async def rename_tenant(request: Request, tenant_id: int, slug: Annotated[str, Form()], username: str = Depends(require_auth)):
    async with get_session() as session:
        await session.execute(update(Tenant).where(Tenant.id == tenant_id).values(slug=slug))
        await session.commit()
    return RedirectResponse(url=f"/tenants/{tenant_id}", status_code=303)

@router.delete("/tenants/{tenant_id}")
async def delete_tenant(request: Request, tenant_id: int, username: str = Depends(require_auth)):
    async with get_session() as session:
        await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
        await session.commit()
    return Response(status_code=200, headers={"HX-Redirect": "/"})

@router.post("/ingest", response_class=HTMLResponse)
async def ingest_file(
    request: Request,
    background_tasks: BackgroundTasks,
    tenant_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    username: str = Depends(require_auth)
):
    valid_extensions = ('.txt', '.md', '.jpg', '.jpeg', '.png', '.webp', '.pdf', '.docx')
    if not file.filename.lower().endswith(valid_extensions):
        return HTMLResponse(f'<div class="text-red-500">Supported formats: {", ".join(valid_extensions)}</div>')

    try:
        # Save securely to a temporary file
        # Create a temporary file with the correct extension so readers know how to parse it
        ext = os.path.splitext(file.filename)[1]
        fd, temp_path = tempfile.mkstemp(suffix=ext)
        with os.fdopen(fd, 'wb') as f:
            shutil.copyfileobj(file.file, f)

        # Pass the temp file path instead of raw bytes
        # The background task will read from this path and is responsible for deleting it
        background_tasks.add_task(ingest_document, tenant_id, file.filename, temp_file_path=temp_path)

        return HTMLResponse(
            f'<div class="text-green-500 mb-2">Processing {file.filename}... refreshing page.</div>'
            f'<script>setTimeout(() => window.location.reload(), 1500);</script>'
        )
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return HTMLResponse(f'<div class="text-red-500">Error reading file</div>')

# Query Route

@router.post("/query", response_class=HTMLResponse)
async def query_rag(
    request: Request,
    tenant_id: Annotated[int, Form()],
    query: Annotated[str, Form()],
    provider: Annotated[str, Form()] = "gemini",
    username: str = Depends(require_auth)
):
    answer = await generate_answer(
        tenant_id,
        query,
        provider=provider
    )

    response_data = {
        "answer": answer,
        "requires_human": False,
        "tenant_id": str(tenant_id),
        "query": query
    }
    full_response_json = json.dumps(response_data, indent=2)

    return templates.TemplateResponse(
        "partials/chat_response.html",
        {
            "request": request,
            "answer": answer,
            "query": query,
            "full_response_json": full_response_json
        }
    )

@router.delete("/documents/{doc_id}", response_class=HTMLResponse)
async def delete_document(request: Request, doc_id: UUID, username: str = Depends(require_auth)):
    async with get_session() as session:
        await session.execute(delete(Document).where(Document.id == doc_id))
        await session.commit()
    return HTMLResponse("")
