import logging
from typing import Any, Dict

from fastapi import HTTPException

from src.modules.contact_sync.mappings import get_contact_mapping, upsert_contact_mapping
from src.modules.contact_sync.schemas import ContactSyncResult, NormalizedContact
from src.modules.contact_sync.providers.espocrm import EspoCrmProvider
from src.modules.tenants import svc_get_tenant_by_slug


logger = logging.getLogger(__name__)

async def sync_chatwoot_contact_payload_to_crm(
    slug: str,
    payload: Dict[str, Any],
    service_name: str = "espocrm",
) -> ContactSyncResult:
    # 1 - Get tenant settings
    tenant_settings = await svc_get_tenant_by_slug(slug)

    # 2 - Extract Chatwoot contact from webhook or direct contact payload
    chatwoot_contact = get_chatwoot_contact_from_payload(payload)

    # 3 - Normalize Chatwoot contact into one internal shape
    normalized_contact = normalize_chatwoot_contact(chatwoot_contact)

    # 4 - Get CRM provider from tenant services
    provider = get_crm_provider(tenant_settings, service_name)

    # 5 - Check if this Chatwoot contact already has a CRM mapping
    existing_mapping = await get_contact_mapping(
        tenant_settings.tenant.id,
        normalized_contact.chatwoot_contact_id,
        service_name,
    )

    # 6 - If mapping exists, update the mapped CRM Contact or Lead
    if existing_mapping:
        external_id, action = await update_mapped_crm_record(
            provider,
            existing_mapping,
            normalized_contact,
        )

        if external_id != existing_mapping.external_id:
            await upsert_contact_mapping(
                tenant_settings.tenant.id,
                normalized_contact.chatwoot_contact_id,
                service_name,
                external_id,
            )

    # 7 - If mapping does not exist, update existing Contact or create/update Lead
    else:
        external_id, action = await find_or_create_crm_record(
            provider,
            normalized_contact,
        )

        # 8 - Save the Chatwoot <-> CRM mapping
        await upsert_contact_mapping(
            tenant_settings.tenant.id,
            normalized_contact.chatwoot_contact_id,
            service_name,
            external_id,
        )

    # 9 - Return sync result
    result = build_contact_sync_result(
        tenant_settings.tenant.id,
        normalized_contact,
        service_name,
        external_id,
        action,
    )
    log_contact_sync_result(result)
    return result


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

    normalized_contact = NormalizedContact(
        chatwoot_contact_id=int(contact_id),
        name=name,
        first_name=first_name,
        last_name=last_name,
        email=_clean_text(chatwoot_contact.get("email")),
        phone=_clean_text(chatwoot_contact.get("phone_number")),
        company_name=_clean_text(additional_attributes.get("company_name")),
        source_payload=chatwoot_contact,
    )

    validate_contact_has_email_or_phone(normalized_contact)
    return normalized_contact


def validate_contact_has_email_or_phone(normalized_contact: NormalizedContact):
    if normalized_contact.email or normalized_contact.phone:
        return

    raise HTTPException(
        status_code=400,
        detail="Chatwoot contact must have email or phone number before CRM sync",
    )


async def sync_chatwoot_contact_to_crm(
    tenant_settings,
    chatwoot_contact: Dict[str, Any],
    service_name: str = "espocrm",
) -> ContactSyncResult:
    normalized_contact = normalize_chatwoot_contact(chatwoot_contact)
    provider = get_crm_provider(tenant_settings, service_name)
    existing_mapping = await get_contact_mapping(
        tenant_settings.tenant.id,
        normalized_contact.chatwoot_contact_id,
        service_name,
    )

    if existing_mapping:
        external_id, action = await update_mapped_crm_record(
            provider,
            existing_mapping,
            normalized_contact,
        )

        if external_id != existing_mapping.external_id:
            await upsert_contact_mapping(
                tenant_settings.tenant.id,
                normalized_contact.chatwoot_contact_id,
                service_name,
                external_id,
            )
    else:
        external_id, action = await find_or_create_crm_record(
            provider,
            normalized_contact,
        )

        await upsert_contact_mapping(
            tenant_settings.tenant.id,
            normalized_contact.chatwoot_contact_id,
            service_name,
            external_id,
        )

    result = build_contact_sync_result(
        tenant_settings.tenant.id,
        normalized_contact,
        service_name,
        external_id,
        action,
    )
    log_contact_sync_result(result)
    return result


def get_chatwoot_contact_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    body = payload.get("body", payload)
    conversation = body.get("conversation") or {}
    body_meta = body.get("meta") or {}
    conversation_meta = conversation.get("meta") or {}

    return (
        body.get("sender")
        or body.get("contact")
        or conversation.get("sender")
        or conversation.get("contact")
        or body_meta.get("sender")
        or body_meta.get("contact")
        or conversation_meta.get("sender")
        or conversation_meta.get("contact")
        or payload
    )


async def update_mapped_crm_record(provider, existing_mapping, normalized_contact):
    if hasattr(provider, "get_record"):
        contact = await provider.get_record("Contact", existing_mapping.external_id)
        if contact:
            updated_contact = await provider.update_contact(
                existing_mapping.external_id,
                normalized_contact,
            )
            return (
                updated_contact.get("id") or existing_mapping.external_id,
                "updated_mapped_contact",
            )

        lead = await provider.get_record("Lead", existing_mapping.external_id)
        if lead:
            updated_lead = await provider.update_lead(
                existing_mapping.external_id,
                normalized_contact,
            )
            return (
                updated_lead.get("id") or existing_mapping.external_id,
                "updated_mapped_lead",
            )

    return await find_or_create_crm_record(provider, normalized_contact)


async def find_or_create_crm_record(provider, normalized_contact):
    existing_contact = await provider.find_contact(normalized_contact)

    if existing_contact:
        external_id = existing_contact["id"]
        await provider.update_contact(external_id, normalized_contact)
        return external_id, "updated_existing_contact"

    existing_lead = await provider.find_lead(normalized_contact)

    if existing_lead:
        external_id = existing_lead["id"]
        await provider.update_lead(external_id, normalized_contact)
        return external_id, "updated_existing_lead"

    new_lead = await provider.create_lead(normalized_contact)
    return new_lead["id"], "created_lead"


def build_contact_sync_result(
    tenant_id: int,
    normalized_contact: NormalizedContact,
    service_name: str,
    external_id: str,
    action: str,
) -> ContactSyncResult:
    return ContactSyncResult(
        tenant_id=tenant_id,
        chatwoot_contact_id=normalized_contact.chatwoot_contact_id,
        service_name=service_name,
        external_id=external_id,
        action=action,
    )


def log_contact_sync_result(result: ContactSyncResult):
    logger.info(
        "Synced Chatwoot contact %s to %s record %s with action=%s",
        result.chatwoot_contact_id,
        result.service_name,
        result.external_id,
        result.action,
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
