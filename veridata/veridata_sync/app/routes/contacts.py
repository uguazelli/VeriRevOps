from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db import get_db_connection
from typing import Annotated, Optional
import uuid
import json

from app.auth import verify_credentials

router = APIRouter(prefix="/tenants/{tenant_id}/contacts", tags=["contacts"], dependencies=[Depends(verify_credentials)])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def list_contacts(request: Request, tenant_id: uuid.UUID):
    async with get_db_connection() as conn:
        tenant = await conn.fetchrow("SELECT * FROM tenants WHERE id = $1", tenant_id)
        contacts = await conn.fetch("SELECT * FROM contacts WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT 100", tenant_id)
    return templates.TemplateResponse("tenants/contacts.html", {"request": request, "tenant": tenant, "contacts": contacts})

@router.post("/", response_class=HTMLResponse)
async def create_contact(
    request: Request,
    tenant_id: uuid.UUID,
    name: Annotated[str, Form()],
    phone: Annotated[str, Form()],
    email: Annotated[str, Form()]
):
    async with get_db_connection() as conn:
        try:
            await conn.execute(
                """
                INSERT INTO contacts (tenant_id, name, phone, email)
                VALUES ($1, $2, $3, $4)
                """,
                tenant_id, name, phone, email
            )
        except Exception as e:
             # Handle constraint violation
             print(f"Error creating contact: {e}")
             pass
    return RedirectResponse(url=f"/tenants/{tenant_id}/contacts", status_code=303)

@router.delete("/{contact_id}", response_class=HTMLResponse)
async def delete_contact(request: Request, tenant_id: uuid.UUID, contact_id: uuid.UUID):
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM contacts WHERE id = $1", contact_id)
    return ""
