import logging
from typing import Any, Dict

from fastapi import HTTPException

from src.modules.contact_sync.mappings import get_contact_mapping, upsert_contact_mapping
from src.modules.contact_sync.models import ContactSyncResult, NormalizedContact
from src.modules.contact_sync.providers.espocrm import EspoCrmProvider
from src.services.tenants import svc_get_tenant_by_slug


logger = logging.getLogger(__name__)


def normalize_chatwoot_contact(chatwoot_contact: Dict[str, Any]) -> NormalizedContact:
    contact_id = chatwoot_contact.get("id")

    if not contact_id:
        raise HTTPException(
            status_code=400,
            detail="Chatwoot contact is missing id",
        )

    additional_attributes = chatwoot_contact.get("additional_attributes") or {}
    name = _clean_text(chatwoot_contact.get("name"))
    first_name, last_name = _split_name(name)

    return NormalizedContact(
        chatwoot_contact_id=int(contact_id),
        name=name,
        first_name=first_name,
        last_name=last_name,
        email=_clean_text(chatwoot_contact.get("email")),
        phone=_clean_text(chatwoot_contact.get("phone_number")),
        company_name=_clean_text(additional_attributes.get("company_name")),
        source_payload=chatwoot_contact,
    )


async def sync_chatwoot_contact_payload_to_crm(
    slug: str,
    payload: Dict[str, Any],
    service_name: str = "espocrm",
) -> ContactSyncResult:
    tenant_settings = await svc_get_tenant_by_slug(slug)
    body = payload.get("body", payload)
    chatwoot_contact = body.get("sender") or body.get("contact") or payload

    return await sync_chatwoot_contact_to_crm(
        tenant_settings,
        chatwoot_contact,
        service_name=service_name,
    )


async def sync_chatwoot_contact_to_crm(
    tenant_settings,
    chatwoot_contact: Dict[str, Any],
    service_name: str = "espocrm",
) -> ContactSyncResult:
    normalized_contact = normalize_chatwoot_contact(chatwoot_contact)
    tenant_id = tenant_settings.tenant.id
    provider = get_crm_provider(tenant_settings, service_name)

    existing_mapping = await get_contact_mapping(
        tenant_id,
        normalized_contact.chatwoot_contact_id,
        service_name,
    )

    if existing_mapping:
        external_contact = await provider.update_contact(
            existing_mapping.external_id,
            normalized_contact,
        )
        external_id = external_contact.get("id") or existing_mapping.external_id
        action = "updated_from_mapping"
    else:
        external_contact = await provider.find_contact(normalized_contact)

        if external_contact:
            external_id = external_contact["id"]
            await provider.update_contact(external_id, normalized_contact)
            action = "linked_existing"
        else:
            external_contact = await provider.create_contact(normalized_contact)
            external_id = external_contact["id"]
            action = "created"

        await upsert_contact_mapping(
            tenant_id,
            normalized_contact.chatwoot_contact_id,
            service_name,
            external_id,
        )

    logger.info(
        "Synced Chatwoot contact %s to %s contact %s with action=%s",
        normalized_contact.chatwoot_contact_id,
        service_name,
        external_id,
        action,
    )

    return ContactSyncResult(
        tenant_id=tenant_id,
        chatwoot_contact_id=normalized_contact.chatwoot_contact_id,
        service_name=service_name,
        external_id=external_id,
        action=action,
    )


def get_crm_provider(tenant_settings, service_name: str):
    service_config = tenant_settings.tenant.services.get(service_name)

    if not service_config:
        raise HTTPException(
            status_code=400,
            detail=f"Tenant has no {service_name} service configured",
        )

    if service_name == "espocrm":
        return EspoCrmProvider(service_config)

    raise HTTPException(
        status_code=400,
        detail=f"Unsupported CRM service: {service_name}",
    )


def _clean_text(value):
    if not isinstance(value, str):
        return None

    value = value.strip()
    return value or None


def _split_name(name):
    if not name:
        return None, None

    parts = name.split(maxsplit=1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else None
    return first_name, last_name

