from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.db import get_db_connection
import uuid
import json

from app.auth import verify_credentials

router = APIRouter(prefix="/tenants/{tenant_id}/configs", tags=["configs"], dependencies=[Depends(verify_credentials)])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
async def list_configs(request: Request, tenant_id: uuid.UUID):
    async with get_db_connection() as conn:
        tenant = await conn.fetchrow("SELECT * FROM tenants WHERE id = $1", tenant_id)
        configs = await conn.fetch("SELECT * FROM config WHERE tenant_id = $1 ORDER BY key", tenant_id)
    return templates.TemplateResponse("tenants/configs.html", {"request": request, "tenant": tenant, "configs": configs})

@router.post("/", response_class=HTMLResponse)
async def create_config(request: Request, tenant_id: uuid.UUID, key: str = Form(...), value: str = Form(...)):
    try:
        value_json = json.loads(value)
    except json.JSONDecodeError:
         # Return error to view (simplified: redirect with error param)
         return RedirectResponse(url=f"/tenants/{tenant_id}/configs?error=Invalid JSON", status_code=303)

    async with get_db_connection() as conn:
        try:
            await conn.execute(
                "INSERT INTO config (tenant_id, key, value) VALUES ($1, $2, $3)",
                tenant_id, key, json.dumps(value_json)
            )
        except Exception as e:
             # Handle unique key constraint
             pass
    return RedirectResponse(url=f"/tenants/{tenant_id}/configs", status_code=303)

@router.delete("/{config_id}", response_class=HTMLResponse)
async def delete_config(request: Request, tenant_id: uuid.UUID, config_id: uuid.UUID):
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM config WHERE id = $1", config_id)
    return ""
