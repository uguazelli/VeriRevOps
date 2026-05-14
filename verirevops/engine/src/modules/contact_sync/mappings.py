from typing import Optional

from src.core.models import ContactMapping, ContactMappingCreate, ContactMappingUpdate
from src.services.contact_mappings import (
    svc_create_contact_mapping,
    svc_list_contact_mappings,
    svc_update_contact_mapping,
)


async def get_contact_mapping(
    tenant_id: int,
    chatwoot_contact_id: int,
    service_name: str,
) -> Optional[ContactMapping]:
    mappings = await svc_list_contact_mappings(
        tenant_id=tenant_id,
        chatwoot_contact_id=chatwoot_contact_id,
        service_name=service_name,
    )

    if not mappings:
        return None

    return mappings[0]


async def upsert_contact_mapping(
    tenant_id: int,
    chatwoot_contact_id: int,
    service_name: str,
    external_id: str,
) -> ContactMapping:
    existing_mapping = await get_contact_mapping(
        tenant_id,
        chatwoot_contact_id,
        service_name,
    )

    if not existing_mapping:
        return await svc_create_contact_mapping(
            ContactMappingCreate(
                tenant_id=tenant_id,
                chatwoot_contact_id=chatwoot_contact_id,
                service_name=service_name,
                external_id=external_id,
            )
        )

    if existing_mapping.external_id == external_id:
        return existing_mapping

    return await svc_update_contact_mapping(
        chatwoot_contact_id,
        ContactMappingUpdate(
            tenant_id=tenant_id,
            service_name=service_name,
            external_id=external_id,
        ),
    )

