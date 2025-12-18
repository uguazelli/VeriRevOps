from fastapi import APIRouter, Request, Form, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db import get_db_connection
from app.auth import verify_credentials
from typing import Annotated
import uuid

router = APIRouter(prefix="/tenants", tags=["tenants"], dependencies=[Depends(verify_credentials)])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def list_tenants(request: Request):
    async with get_db_connection() as conn:
        rows = await conn.fetch("SELECT * FROM tenants ORDER BY created_at DESC")
    return templates.TemplateResponse("tenants/list.html", {"request": request, "tenants": rows})

@router.post("/", response_class=HTMLResponse)
async def create_tenant(request: Request, name: Annotated[str, Form()], slug: Annotated[str, Form()]):
    async with get_db_connection() as conn:
        try:
            await conn.execute("INSERT INTO tenants (name, slug) VALUES ($1, $2)", name, slug)
        except Exception as e:
            # Handle unique constraint violation or other errors
             return templates.TemplateResponse("tenants/list.html", {
                "request": request,
                "tenants": await conn.fetch("SELECT * FROM tenants ORDER BY created_at DESC"),
                "error": f"Error creating tenant: {e}"
            })

    # Return updated list or redirect
    return RedirectResponse(url="/tenants", status_code=303)

@router.get("/{tenant_id}/edit", response_class=HTMLResponse)
async def edit_tenant_form(request: Request, tenant_id: uuid.UUID):
    async with get_db_connection() as conn:
        tenant = await conn.fetchrow("SELECT * FROM tenants WHERE id = $1", tenant_id)
    return templates.TemplateResponse("tenants/edit.html", {"request": request, "tenant": tenant})

@router.post("/{tenant_id}", response_class=HTMLResponse)
async def update_tenant(request: Request, tenant_id: uuid.UUID, name: Annotated[str, Form()], slug: Annotated[str, Form()]):
    async with get_db_connection() as conn:
        await conn.execute("UPDATE tenants SET name = $1, slug = $2 WHERE id = $3", name, slug, tenant_id)
    return RedirectResponse(url="/tenants", status_code=303)

@router.delete("/{tenant_id}", response_class=HTMLResponse)
async def delete_tenant(request: Request, tenant_id: uuid.UUID):
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)

    # Return empty string or updated list row if doing granular updates.
    # For simplicity, we can redirect or return the updated list (HTMX handles this).
    # Since DELETE usually needs a response to swap, we'll return a 200 OK via HTMX mechanism
    # but HTMX delete often expects the element to disappear.
    return ""
