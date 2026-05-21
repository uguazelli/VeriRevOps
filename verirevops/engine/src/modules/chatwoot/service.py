import asyncio
import logging
import os

from src.modules.chatwoot.classifier import (
    classify_chatwoot_message,
    get_classification_data,
    get_classification_category,
)
from src.modules.chatwoot.client import (
    get_last_ten_messages,
    send_message_to_chatwoot,
    update_conversation_status_to_open,
)
from src.modules.chatwoot.payload import (
    get_message_kind,
    get_text_message_content,
    process_chatwoot_payload,
)
from src.modules.chatwoot.media import (
    analyze_chatwoot_image,
    transcribe_chatwoot_audio,
)
from src.modules.chatwoot.responses import (
    respond_to_chitchat,
    respond_to_handoff,
    respond_with_rag,
)
from src.modules.contact_sync.service import sync_chatwoot_contact_payload_to_crm
from src.modules.conversation_summary.crm import get_conversation_summary_crm_handler
from src.modules.conversation_summary.summarizer import summarize_chatwoot_messages
from src.modules.tenants import (
    svc_get_tenant_by_slug,
    svc_has_available_subscription_usage,
    svc_increment_subscription_usage,
)

logger = logging.getLogger(__name__)

DEFAULT_BOT_PROCESSING_TIMEOUT_SECONDS = 75


async def process_chatwoot_webhook(slug: str, payload: dict):
    tenant_settings = None
    should_count_usage = False

    try:
        # 1 - Process and validate Chatwoot payload to decide if it requires a response
        should_respond = process_chatwoot_payload(payload)
        if not should_respond["should_respond"]:
            return

        # 2 - Get tenant settings
        tenant_settings = await svc_get_tenant_by_slug(slug)

        # 3 - Check subscription quota before running bot work
        has_quota = await svc_has_available_subscription_usage(tenant_settings.tenant.id)
        if not has_quota:
            return

        should_count_usage = True
        await asyncio.wait_for(
            process_chatwoot_bot_message(slug, tenant_settings, payload),
            timeout=get_bot_processing_timeout_seconds(),
        )

    except asyncio.TimeoutError:
        logger.warning(
            "Chatwoot bot processing timed out for tenant slug '%s' after %s seconds",
            slug,
            get_bot_processing_timeout_seconds(),
        )
        await open_chatwoot_conversation_after_failure(
            tenant_settings,
            payload,
            slug,
            "timeout",
        )
    except Exception:
        await open_chatwoot_conversation_after_failure(
            tenant_settings,
            payload,
            slug,
            "failure",
        )
        log_chatwoot_webhook_failure(slug)
    finally:
        if should_count_usage and tenant_settings:
            await increment_subscription_usage_after_processing(tenant_settings, slug)


async def process_chatwoot_bot_message(slug: str, tenant_settings, payload: dict):
    current_message = await get_current_chatwoot_message(payload)
    message_history = await get_last_ten_messages(tenant_settings, payload)
    classification = await classify_chatwoot_message(message_history, current_message)
    response, category = await build_chatwoot_response_for_classification(
        tenant_settings,
        message_history,
        current_message,
        classification,
    )

    if response:
        await send_message_to_chatwoot(tenant_settings, payload, response)

    if category == "HANDOFF":
        await handle_chatwoot_handoff(slug, tenant_settings, payload, message_history)


async def get_current_chatwoot_message(payload: dict) -> str:
    message_kind = get_message_kind(payload)

    if message_kind == "audio":
        return await transcribe_chatwoot_audio(payload)

    if message_kind == "image":
        return await analyze_chatwoot_image(payload)

    return get_text_message_content(payload)


async def build_chatwoot_response_for_classification(
    tenant_settings,
    message_history,
    current_message: str,
    classification: dict,
):
    category = get_classification_category(classification)
    handoff_reason = get_classification_data(classification).get("reason")

    if category == "CHITCHAT":
        return await respond_to_chitchat(current_message), category

    if category == "RETRIEVAL":
        return await build_chatwoot_rag_response(
            tenant_settings,
            message_history,
            current_message,
        )

    if category == "OUT_OF_SCOPE":
        handoff_reason = handoff_reason or "Request is outside basic approved business answers."

    return await respond_to_handoff(
        message_history,
        current_message,
        handoff_reason=handoff_reason,
    ), "HANDOFF"


async def build_chatwoot_rag_response(
    tenant_settings,
    message_history,
    current_message: str,
):
    response = await respond_with_rag(tenant_settings, current_message)

    if isinstance(response, dict) and response.get("handoff_required") is True:
        return await respond_to_handoff(
            message_history,
            current_message,
            handoff_reason=response.get("reason"),
        ), "HANDOFF"

    return response, "RETRIEVAL"


async def handle_chatwoot_handoff(slug: str, tenant_settings, payload: dict, message_history):
    await update_conversation_status_to_open(tenant_settings, payload)
    await sync_crm_contact_after_handoff(slug, payload)
    await add_crm_handoff_summary(tenant_settings, payload, message_history)


def get_bot_processing_timeout_seconds() -> int:
    raw_timeout = os.getenv("CHATWOOT_BOT_TIMEOUT_SECONDS")

    if not raw_timeout:
        return DEFAULT_BOT_PROCESSING_TIMEOUT_SECONDS

    try:
        timeout = int(raw_timeout)
    except ValueError:
        logger.warning(
            "Invalid CHATWOOT_BOT_TIMEOUT_SECONDS value '%s'; using default %s",
            raw_timeout,
            DEFAULT_BOT_PROCESSING_TIMEOUT_SECONDS,
        )
        return DEFAULT_BOT_PROCESSING_TIMEOUT_SECONDS

    return max(1, timeout)


async def open_chatwoot_conversation_after_failure(
    tenant_settings,
    payload: dict,
    slug: str,
    reason: str,
):
    if not tenant_settings:
        return

    try:
        await update_conversation_status_to_open(tenant_settings, payload)
        logger.info(
            "Opened Chatwoot conversation for tenant slug '%s' after bot %s",
            slug,
            reason,
        )
    except Exception:
        logger.exception(
            "Failed to open Chatwoot conversation for tenant slug '%s' after bot %s",
            slug,
            reason,
        )


async def increment_subscription_usage_after_processing(tenant_settings, slug: str):
    try:
        await svc_increment_subscription_usage(tenant_settings.tenant.id)
    except Exception:
        logger.exception(
            "Failed to increment subscription usage for tenant slug '%s'",
            slug,
        )


async def sync_crm_contact_after_handoff(slug: str, payload: dict):
    try:
        await sync_chatwoot_contact_payload_to_crm(slug, payload)
    except Exception:
        logger.exception(
            "Failed to create or update CRM contact during Chatwoot handoff for tenant slug '%s'",
            slug,
        )


async def add_crm_handoff_summary(tenant_settings, payload: dict, message_history):
    try:
        summary = await summarize_chatwoot_messages(message_history)
        if not summary:
            return

        crm_handler = get_conversation_summary_crm_handler(tenant_settings)
        crm_target = await crm_handler.resolve_summary_target(payload)
        await crm_handler.send_summary(crm_target, summary)
    except Exception:
        logger.exception("Failed to add Chatwoot handoff summary to CRM")


def log_chatwoot_webhook_failure(slug: str):
    logger.exception("Failed to process Chatwoot webhook for tenant slug '%s'", slug)
