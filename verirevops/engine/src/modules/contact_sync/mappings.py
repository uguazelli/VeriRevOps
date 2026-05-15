from typing import List, Optional

from fastapi import HTTPException
from sqlmodel import select

from src.core.db import get_session
from src.core.models import ContactMapping, ContactMappingCreate, ContactMappingUpdate


async def svc_list_contact_mappings(
    tenant_id: Optional[int] = None,
    chatwoot_contact_id: Optional[int] = None,
    service_name: Optional[str] = None,
) -> List[ContactMapping]:
    async with get_session() as db:
        query = select(ContactMapping)
        if tenant_id:
            query = query.where(ContactMapping.tenant_id == tenant_id)
        if chatwoot_contact_id:
            query = query.where(ContactMapping.chatwoot_contact_id == chatwoot_contact_id)
        if service_name:
            query = query.where(ContactMapping.service_name == service_name)

        result = await db.execute(query)
        return result.scalars().all()


async def svc_create_contact_mapping(
    mapping_data: ContactMappingCreate,
) -> ContactMapping:
    async with get_session() as db:
        query = select(ContactMapping).where(
            ContactMapping.tenant_id == mapping_data.tenant_id,
            ContactMapping.chatwoot_contact_id == mapping_data.chatwoot_contact_id,
            ContactMapping.service_name == mapping_data.service_name,
        )
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Contact mapping already exists")

        mapping = ContactMapping(**mapping_data.model_dump())
        db.add(mapping)
        await db.commit()
        await db.refresh(mapping)
        return mapping


async def svc_update_contact_mapping(
    chatwoot_contact_id: int,
    mapping_data: ContactMappingUpdate,
) -> ContactMapping:
    async with get_session() as db:
        query = select(ContactMapping).where(
            ContactMapping.tenant_id == mapping_data.tenant_id,
            ContactMapping.chatwoot_contact_id == chatwoot_contact_id,
            ContactMapping.service_name == mapping_data.service_name,
        )
        result = await db.execute(query)
        mapping = result.scalar_one_or_none()

        if not mapping:
            raise HTTPException(status_code=404, detail="Contact mapping not found")

        mapping.external_id = mapping_data.external_id

        await db.commit()
        await db.refresh(mapping)
        return mapping


async def svc_delete_contact_mapping(
    mapping_id: int,
) -> int:
    async with get_session() as db:
        query = select(ContactMapping).where(ContactMapping.id == mapping_id)
        result = await db.execute(query)
        mapping = result.scalar_one_or_none()

        if mapping:
            await db.delete(mapping)
            await db.commit()
            return 1

        return 0


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

