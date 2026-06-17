import secrets

from fastapi import APIRouter, Depends, HTTPException, Request

from src.core.auth import require_auth
from src.core.models import ContactMappingBase, User
from src.modules.auth.service import get_tenant_by_slug_simple, get_tenant_webhook_token
from src.modules.contact_sync.mappings import (
    svc_create_contact_mapping,
    svc_delete_contact_mapping,
    svc_list_contact_mappings,
    svc_update_contact_mapping,
)
from src.modules.contact_sync.schemas import (
    ContactMappingResponse,
    ContactMappingUpdate,
    ContactSyncResult,
)
from src.modules.contact_sync.service import sync_chatwoot_contact_payload_to_crm


router = APIRouter()


async def _validate_webhook(slug: str, request: Request):
    tenant = await get_tenant_by_slug_simple(slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    webhook_token = await get_tenant_webhook_token(tenant.id)
    if webhook_token:
        provided = request.headers.get("X-Webhook-Token", "")
        if not provided or not secrets.compare_digest(provided, webhook_token):
            raise HTTPException(status_code=401, detail="Invalid or missing X-Webhook-Token")

    return tenant


@router.post("/contact-sync/chatwoot/{slug}", response_model=ContactSyncResult)
async def sync_chatwoot_contact(
    slug: str,
    payload: dict,
    request: Request,
    service_name: str = "espocrm",
):
    await _validate_webhook(slug, request)
    return await sync_chatwoot_contact_payload_to_crm(slug, payload, service_name=service_name)


@router.get("/contact_mappings", response_model=list[ContactMappingResponse])
async def list_contact_mappings(
    user: User = Depends(require_auth),
    tenant_id: int = None,
    chatwoot_contact_id: int = None,
    service_name: str = None,
):
    # Scope non-superadmin users to their own tenant
    if user.role != "superadmin":
        tenant_id = user.tenant_id
    return await svc_list_contact_mappings(tenant_id, chatwoot_contact_id, service_name)


@router.post("/contact_mappings", response_model=ContactMappingResponse)
async def create_contact_mapping(
    mapping_data: ContactMappingBase,
    user: User = Depends(require_auth),
):
    if user.role != "superadmin" and user.tenant_id != mapping_data.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied to this tenant")
    return await svc_create_contact_mapping(mapping_data)


@router.put("/contact_mappings/{chatwoot_contact_id}", response_model=ContactMappingResponse)
async def update_contact_mapping(
    chatwoot_contact_id: int,
    mapping_data: ContactMappingUpdate,
    user: User = Depends(require_auth),
):
    return await svc_update_contact_mapping(chatwoot_contact_id, mapping_data)


@router.delete("/contact_mappings/{mapping_id}")
async def delete_contact_mapping(
    mapping_id: int,
    user: User = Depends(require_auth),
):
    count = await svc_delete_contact_mapping(mapping_id)
    return {"deleted_count": count}
