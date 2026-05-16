from fastapi import HTTPException

from src.modules.contact_sync.service import get_crm_provider
from src.modules.conversation_summary.crm.base import ConversationSummaryCrmHandler
from src.modules.conversation_summary.crm.espocrm import EspoCrmConversationSummaryHandler


_CRM_SUMMARY_HANDLERS = {
    EspoCrmConversationSummaryHandler.service_name: EspoCrmConversationSummaryHandler,
}


def get_conversation_summary_crm_handler(
    tenant_settings,
    service_name: str = "espocrm",
) -> ConversationSummaryCrmHandler:
    handler_class = _CRM_SUMMARY_HANDLERS.get(service_name)

    if not handler_class:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported CRM service for conversation summary: {service_name}",
        )

    provider = get_crm_provider(tenant_settings, service_name)
    return handler_class(tenant_settings, provider)
