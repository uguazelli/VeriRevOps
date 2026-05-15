from typing import List

from fastapi import APIRouter

from src.core.models import (
    ContactMappingCreate,
    ContactMappingResponse,
    ContactMappingUpdate,
)
from src.modules.contact_sync.mappings import (
    svc_create_contact_mapping,
    svc_delete_contact_mapping,
    svc_list_contact_mappings,
    svc_update_contact_mapping,
)
from src.modules.contact_sync.models import ContactSyncResult
from src.modules.contact_sync.service import sync_chatwoot_contact_payload_to_crm


router = APIRouter()


@router.post("/contact-sync/chatwoot/{slug}", response_model=ContactSyncResult)
async def sync_chatwoot_contact(
    slug: str,
    payload: dict,
    service_name: str = "espocrm",
):
    """
    Sync one Chatwoot contact payload to the configured CRM.
    """
    return await sync_chatwoot_contact_payload_to_crm(
        slug,
        payload,
        service_name=service_name,
    )


@router.get("/contact_mappings", response_model=List[ContactMappingResponse])
async def list_contact_mappings(
    tenant_id: int = None,
    chatwoot_contact_id: int = None,
    service_name: str = None,
):
    """
    List contact mappings with optional filtering.
    """
    return await svc_list_contact_mappings(
        tenant_id,
        chatwoot_contact_id,
        service_name,
    )


@router.post("/contact_mappings", response_model=ContactMappingResponse)
async def create_contact_mapping(mapping_data: ContactMappingCreate):
    """
    Create a new contact mapping.
    """
    return await svc_create_contact_mapping(mapping_data)


@router.put("/contact_mappings/{chatwoot_contact_id}", response_model=ContactMappingResponse)
async def update_contact_mapping(
    chatwoot_contact_id: int,
    mapping_data: ContactMappingUpdate,
):
    """
    Update an existing contact mapping.
    """
    return await svc_update_contact_mapping(chatwoot_contact_id, mapping_data)


@router.delete("/contact_mappings/{mapping_id}")
async def delete_contact_mapping(mapping_id: int):
    """
    Delete a contact mapping by database ID.
    """
    count = await svc_delete_contact_mapping(mapping_id)
    return {"deleted_count": count}
