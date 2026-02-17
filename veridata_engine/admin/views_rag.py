import logging
import uuid
from typing import Annotated, Optional
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, select
from admin.auth import authentication_backend
from bot.core.config import settings
from bot.core.db import get_session
from bot.models.client import Client
from rag.models.sql import Document
from rag.services.ingest_service import ingest_document
from rag.services.rag_service import generate_answer
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)


logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="admin/templates/rag")

router = APIRouter()


async def require_auth(request: Request):
    """Check if user is authenticated via session."""
    is_authenticated = await authentication_backend.authenticate(request)
    if not is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/admin-bot/login"},
        )
    return True


async def get_clients():
    result = []
    async for session in get_session():
        stmt = select(Client.id, Client.name, Client.slug).order_by(Client.id.desc())
        res = await session.execute(stmt)
        clients = res.all()
        # Convert to dict or object compatible with template
        for c in clients:
            result.append({"id": c.id, "name": c.name, "slug": c.slug})
    return result


async def get_client_documents(client_id: int):
    results = []
    async for session in get_session():
        stmt = (
            select(
                Document.filename,
                func.max(Document.created_at).label("created_at"),
                func.count().label("chunk_count"),
            )
            .where(Document.client_id == client_id)
            .group_by(Document.filename)
            .order_by(func.max(Document.created_at).desc())
        )
        res = await session.execute(stmt)
        rows = res.all()
        for r in rows:
            results.append({
                "filename": r.filename,
                "created_at": r.created_at,
                "chunk_count": r.chunk_count
            })
    return results


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, authenticated: bool = Depends(require_auth)):
    clients = await get_clients()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tenants": clients, # Template expects 'tenants' (renamed logic but kept var name for compatibility)
            "selected_tenant": None,
            "username": settings.admin_user,
        },
    )



@router.get("/logout")
async def logout(request: Request):
    """Logout and clear session."""
    await authentication_backend.logout(request)
    return RedirectResponse(url="/admin-bot/login", status_code=status.HTTP_303_SEE_OTHER)



@router.get("/clients/{client_id}", response_class=HTMLResponse)
async def view_client(
    request: Request, client_id: int, authenticated: bool = Depends(require_auth)
):
    clients = await get_clients()
    documents = await get_client_documents(client_id)

    client_data = {"id": client_id, "name": "Unknown", "preferred_languages": ""}

    async for session in get_session():
        res = await session.execute(select(Client).where(Client.id == client_id))
        client = res.scalars().first()
        if client:
            client_data["name"] = client.name
            # client_data["preferred_languages"] = ... # Client model needs this field if we want it

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "tenants": clients,
            "selected_tenant": client_data,
            "documents": documents,
            "username": settings.admin_user,
        },
    )


@router.post("/query", response_class=HTMLResponse)
async def query_rag_web(
    request: Request,
    tenant_id: Annotated[int, Form()], # Form field name might still be 'tenant_id' in template
    query: Annotated[str, Form()],
    provider: Annotated[str, Form()] = "gemini",
    session_id: Annotated[Optional[str], Form()] = None,
    authenticated: bool = Depends(require_auth),
):
    if not session_id:
        session_id = uuid.uuid4()
    else:
        try:
            session_id = uuid.UUID(session_id)
        except:
             session_id = uuid.uuid4()

    answer, session_id, _ = await generate_answer(
        client_id=tenant_id,
        query=query,
        session_id=session_id,
    )
    return templates.TemplateResponse(
        "partials/chat_response.html",
        {
            "request": request,
            "answer": answer,
            "query": query,
            "session_id": str(session_id),
        },
    )


@router.post("/ingest", response_class=HTMLResponse)
async def ingest_file_web(
    request: Request,
    background_tasks: BackgroundTasks,
    tenant_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
    authenticated: bool = Depends(require_auth),
):
    if not file.filename.lower().endswith(
        (".txt", ".md", ".jpg", ".jpeg", ".png", ".webp")
    ):
        return HTMLResponse(
            '<div class="text-red-500">Supported formats: .txt, .md, .jpg, .png, .webp</div>'
        )

    content = await file.read()
    text_content = None
    file_bytes = None

    if file.filename.lower().endswith((".txt", ".md")):
        text_content = content.decode("utf-8")
    else:
        file_bytes = content

    background_tasks.add_task(
        ingest_document,
        tenant_id,
        file.filename,
        content=text_content,
        file_bytes=file_bytes,
    )
    return HTMLResponse(
        f'<div class="text-green-500 mb-2">Started processing {file.filename}... check back soon.</div>'
    )


@router.delete("/clients/{client_id}/documents", response_class=HTMLResponse)
async def delete_document_web(
    request: Request,
    client_id: int,
    filename: str,
    authenticated: bool = Depends(require_auth),
):
    async for session in get_session():
        stmt = delete(Document).where(
            Document.client_id == client_id, Document.filename == filename
        )
        await session.execute(stmt)
        await session.commit()
    return HTMLResponse("")
