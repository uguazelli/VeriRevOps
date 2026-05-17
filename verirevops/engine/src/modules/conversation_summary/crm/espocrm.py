import logging

from fastapi import HTTPException

from src.modules.contact_sync.mappings import get_contact_mapping
from src.modules.contact_sync.service import (
    get_chatwoot_contact_from_payload,
    normalize_chatwoot_contact,
)
from src.modules.conversation_summary.crm.base import ConversationSummaryCrmHandler
from src.modules.conversation_summary.schemas import CrmSummaryTarget


logger = logging.getLogger(__name__)


class EspoCrmConversationSummaryHandler(ConversationSummaryCrmHandler):
    service_name = "espocrm"

    async def resolve_summary_target(self, payload: dict) -> CrmSummaryTarget:
        chatwoot_contact = get_chatwoot_contact_from_payload(payload)
        normalized_contact = normalize_chatwoot_contact(chatwoot_contact)

        existing_mapping = await get_contact_mapping(
            self.tenant_settings.tenant.id,
            normalized_contact.chatwoot_contact_id,
            self.service_name,
        )

        if existing_mapping:
            mapped_target = await self._resolve_mapped_target(existing_mapping.external_id)
            if mapped_target:
                return mapped_target

        contact = await self.provider.find_contact(normalized_contact)
        if contact:
            return CrmSummaryTarget(
                entity_type="Contact",
                external_id=contact["id"],
                source="contact_search",
            )

        lead = await self.provider.find_lead(normalized_contact)
        if lead:
            return CrmSummaryTarget(
                entity_type="Lead",
                external_id=lead["id"],
                source="lead_search",
            )

        raise HTTPException(
            status_code=404,
            detail="No EspoCRM Contact or Lead found for Chatwoot contact",
        )

    async def send_summary(self, target: CrmSummaryTarget, summary: str):
        note = await self.provider.create_stream_note(
            target.entity_type,
            target.external_id,
            summary,
        )
        logger.info(
            "Created EspoCRM summary note id=%s parent_type=%s parent_id=%s",
            note.get("id"),
            target.entity_type,
            target.external_id,
        )
        return note

    async def _resolve_mapped_target(self, external_id: str):
        contact = await self.provider.get_record("Contact", external_id)
        if contact:
            return CrmSummaryTarget(
                entity_type="Contact",
                external_id=external_id,
                source="mapping_contact",
            )

        lead = await self.provider.get_record("Lead", external_id)
        if lead:
            return CrmSummaryTarget(
                entity_type="Lead",
                external_id=external_id,
                source="mapping_lead",
            )

        return None
