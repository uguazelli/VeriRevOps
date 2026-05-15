import logging

from fastapi import HTTPException

from src.modules.contact_sync.mappings import get_contact_mapping
from src.modules.contact_sync.service import (
    get_chatwoot_contact_from_payload,
    get_crm_provider,
    normalize_chatwoot_contact,
)
from src.modules.conversation_summary.models import CrmSummaryTarget


logger = logging.getLogger(__name__)


async def resolve_crm_summary_target(
    tenant_settings,
    payload,
    service_name: str = "espocrm",
) -> CrmSummaryTarget:
    provider = get_crm_provider(tenant_settings, service_name)
    chatwoot_contact = get_chatwoot_contact_from_payload(payload)
    normalized_contact = normalize_chatwoot_contact(chatwoot_contact)

    existing_mapping = await get_contact_mapping(
        tenant_settings.tenant.id,
        normalized_contact.chatwoot_contact_id,
        service_name,
    )

    if existing_mapping:
        mapped_target = await resolve_mapped_crm_target(
            provider,
            existing_mapping.external_id,
        )
        if mapped_target:
            return mapped_target

    contact = await provider.find_contact(normalized_contact)
    if contact:
        return CrmSummaryTarget(
            entity_type="Contact",
            external_id=contact["id"],
            source="contact_search",
        )

    if hasattr(provider, "find_lead"):
        lead = await provider.find_lead(normalized_contact)
        if lead:
            return CrmSummaryTarget(
                entity_type="Lead",
                external_id=lead["id"],
                source="lead_search",
            )

    raise HTTPException(
        status_code=404,
        detail="No CRM Contact or Lead found for Chatwoot contact",
    )


async def resolve_mapped_crm_target(provider, external_id: str):
    if hasattr(provider, "get_record"):
        contact = await provider.get_record("Contact", external_id)
        if contact:
            return CrmSummaryTarget(
                entity_type="Contact",
                external_id=external_id,
                source="mapping_contact",
            )

        lead = await provider.get_record("Lead", external_id)
        if lead:
            return CrmSummaryTarget(
                entity_type="Lead",
                external_id=external_id,
                source="mapping_lead",
            )

    return None


async def send_summary_to_crm(provider, target: CrmSummaryTarget, summary: str):
    note = await provider.create_stream_note(
        target.entity_type,
        target.external_id,
        summary,
    )
    logger.info(
        "Created CRM summary note id=%s parent_type=%s parent_id=%s",
        note.get("id"),
        target.entity_type,
        target.external_id,
    )
    return note
