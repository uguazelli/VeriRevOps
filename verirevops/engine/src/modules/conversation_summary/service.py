import logging

from src.core.models import ChatMessageCreate
from src.modules.chatwoot.client import (
    fetch_conversation_messages_after,
    get_chatwoot_service,
)
from src.modules.chatwoot.payload import get_chatwoot_conversation_id
from src.modules.contact_sync.service import get_crm_provider
from src.modules.conversation_summary.crm import (
    resolve_crm_summary_target,
    send_summary_to_crm,
)
from src.modules.conversation_summary.models import ConversationSummaryResult
from src.modules.conversation_summary.payload import (
    get_latest_message_id,
    should_summarize_chatwoot_payload,
)
from src.modules.conversation_summary.summarizer import summarize_chatwoot_messages
from src.modules.chatwoot.message_tracking import svc_list_chat_messages, svc_upsert_chat_message
from src.services.tenants import svc_get_tenant_by_slug


logger = logging.getLogger(__name__)


async def process_conversation_summary_webhook(slug: str, payload: dict):
    try:
        await summarize_resolved_chatwoot_conversation(slug, payload)
    except Exception:
        logger.exception("Failed to summarize resolved Chatwoot conversation for tenant '%s'", slug)


async def summarize_resolved_chatwoot_conversation(
    slug: str,
    payload: dict,
    provider: str = "gemini",
    crm_service_name: str = "espocrm",
) -> ConversationSummaryResult:

    # 1 - Validate this is a resolved Chatwoot conversation notification
    if not should_summarize_chatwoot_payload(payload):
        return ConversationSummaryResult(
            tenant_id=0,
            chatwoot_account_id=0,
            chatwoot_conversation_id=0,
            after_message_id=0,
            action="skipped_not_resolved",
        )

    # 2 - Get tenant and Chatwoot settings
    tenant_settings = await svc_get_tenant_by_slug(slug)
    chatwoot_service = get_chatwoot_service(tenant_settings)
    tenant_id = tenant_settings.tenant.id
    chatwoot_account_id = int(chatwoot_service.account_id)
    chatwoot_conversation_id = get_chatwoot_conversation_id(payload)

    # 3 - Get last summarized message marker from chat_messages
    after_message_id = await get_last_summary_message_id(
        tenant_id,
        chatwoot_account_id,
        chatwoot_conversation_id,
    )

    # 4 - Fetch Chatwoot messages after the last summary marker
    messages = await fetch_conversation_messages_after(
        tenant_settings,
        chatwoot_conversation_id,
        after_message_id,
    )

    if not isinstance(messages, list) or not messages:
        return build_summary_result(
            tenant_id,
            chatwoot_account_id,
            chatwoot_conversation_id,
            after_message_id,
            action="skipped_no_new_messages",
        )

    latest_message_id = get_latest_message_id(messages)
    if latest_message_id is None or latest_message_id <= after_message_id:
        return build_summary_result(
            tenant_id,
            chatwoot_account_id,
            chatwoot_conversation_id,
            after_message_id,
            latest_message_id=latest_message_id,
            action="skipped_no_newer_marker",
        )

    # 5 - Summarize newly fetched messages
    summary = await summarize_chatwoot_messages(messages, provider=provider)
    if not summary:
        return build_summary_result(
            tenant_id,
            chatwoot_account_id,
            chatwoot_conversation_id,
            after_message_id,
            latest_message_id=latest_message_id,
            action="skipped_empty_summary",
        )

    # 6 - Resolve CRM target: Contact first, Lead second
    crm_target = await resolve_crm_summary_target(
        tenant_settings,
        payload,
        service_name=crm_service_name,
    )
    crm_provider = get_crm_provider(tenant_settings, crm_service_name)

    # 7 - Create CRM stream note
    await send_summary_to_crm(crm_provider, crm_target, summary)

    # 8 - Update chat_messages marker only after CRM note succeeds
    await update_summary_message_marker(
        tenant_id,
        chatwoot_account_id,
        chatwoot_conversation_id,
        latest_message_id,
    )

    # 9 - Return result
    result = build_summary_result(
        tenant_id,
        chatwoot_account_id,
        chatwoot_conversation_id,
        after_message_id,
        latest_message_id=latest_message_id,
        crm_entity_type=crm_target.entity_type,
        crm_external_id=crm_target.external_id,
        action="summarized",
    )
    log_summary_result(result)
    return result


async def get_last_summary_message_id(
    tenant_id: int,
    chatwoot_account_id: int,
    chatwoot_conversation_id: int,
) -> int:
    tracked_messages = await svc_list_chat_messages(
        tenant_id,
        chatwoot_account_id,
        chatwoot_conversation_id,
    )

    if not tracked_messages:
        return 0

    latest_tracking_record = max(
        tracked_messages,
        key=lambda message: message.id or 0,
    )
    return latest_tracking_record.message_id


async def update_summary_message_marker(
    tenant_id: int,
    chatwoot_account_id: int,
    chatwoot_conversation_id: int,
    message_id: int,
):
    return await svc_upsert_chat_message(
        ChatMessageCreate(
            tenant_id=tenant_id,
            chatwoot_account_id=chatwoot_account_id,
            chatwoot_conversation_id=chatwoot_conversation_id,
            message_id=message_id,
        )
    )


def build_summary_result(
    tenant_id: int,
    chatwoot_account_id: int,
    chatwoot_conversation_id: int,
    after_message_id: int,
    latest_message_id=None,
    crm_entity_type=None,
    crm_external_id=None,
    action: str = "unknown",
) -> ConversationSummaryResult:
    return ConversationSummaryResult(
        tenant_id=tenant_id,
        chatwoot_account_id=chatwoot_account_id,
        chatwoot_conversation_id=chatwoot_conversation_id,
        after_message_id=after_message_id,
        latest_message_id=latest_message_id,
        crm_entity_type=crm_entity_type,
        crm_external_id=crm_external_id,
        action=action,
    )


def log_summary_result(result: ConversationSummaryResult):
    logger.info(
        "Conversation summary result tenant=%s account=%s conversation=%s action=%s latest_message=%s crm_target=%s:%s",
        result.tenant_id,
        result.chatwoot_account_id,
        result.chatwoot_conversation_id,
        result.action,
        result.latest_message_id,
        result.crm_entity_type,
        result.crm_external_id,
    )
