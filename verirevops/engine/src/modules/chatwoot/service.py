import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from src.modules.chatwoot.classifier import (
    classify_chatwoot_message,
    get_classification_category,
    get_classification_data,
)
from src.modules.chatwoot.client import (
    get_last_ten_messages,
    send_message_to_chatwoot,
    update_conversation_status_to_open,
)
from src.modules.chatwoot.media import analyze_chatwoot_image, transcribe_chatwoot_audio
from src.modules.chatwoot.payload import (
    get_message_kind,
    get_text_message_content,
    process_chatwoot_payload,
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


@dataclass
class ChatwootFlowContext:
    slug: str
    payload: dict
    tenant_settings: Any = None
    should_respond: bool = False
    should_count_usage: bool = False
    current_message: str = ""
    message_history: Any = field(default_factory=list)
    classification: dict = field(default_factory=dict)
    category: str | None = None
    response: Any = None
    response_sent: bool = False
    handoff_required: bool = False
    handoff_reason: str | None = None


async def process_chatwoot_webhook(slug: str, payload: dict):
    ctx = ChatwootFlowContext(slug=slug, payload=payload)

    try:
        check_payload_should_respond(ctx)
        if not ctx.should_respond:
            return

        await load_tenant_settings(ctx)
        await check_subscription_quota(ctx)
        if not ctx.should_count_usage:
            return

        await asyncio.wait_for(
            run_chatwoot_message_flow(ctx),
            timeout=get_bot_processing_timeout_seconds(),
        )

    except asyncio.TimeoutError:
        logger.warning(
            "Chatwoot bot processing timed out for tenant slug '%s' after %s seconds",
            ctx.slug,
            get_bot_processing_timeout_seconds(),
        )
        await open_chatwoot_conversation_after_failure(ctx, "timeout")
    except Exception:
        await open_chatwoot_conversation_after_failure(ctx, "failure")
        log_chatwoot_webhook_failure(ctx)
    finally:
        await increment_subscription_usage_if_needed(ctx)


async def run_chatwoot_message_flow(ctx: ChatwootFlowContext):
    await resolve_current_message(ctx)
    await fetch_message_history(ctx)
    await classify_current_message(ctx)
    await build_bot_response(ctx)
    await send_bot_response(ctx)
    await run_handoff_flow_if_needed(ctx)


def check_payload_should_respond(ctx: ChatwootFlowContext):
    decision = process_chatwoot_payload(ctx.payload)
    ctx.should_respond = decision["should_respond"]


async def load_tenant_settings(ctx: ChatwootFlowContext):
    ctx.tenant_settings = await svc_get_tenant_by_slug(ctx.slug)


async def check_subscription_quota(ctx: ChatwootFlowContext):
    ctx.should_count_usage = await svc_has_available_subscription_usage(
        ctx.tenant_settings.tenant.id
    )


async def resolve_current_message(ctx: ChatwootFlowContext):
    message_kind = get_message_kind(ctx.payload)

    if message_kind == "audio":
        ctx.current_message = await transcribe_chatwoot_audio(ctx.payload)
        return

    if message_kind == "image":
        ctx.current_message = await analyze_chatwoot_image(ctx.payload)
        return

    ctx.current_message = get_text_message_content(ctx.payload)


async def fetch_message_history(ctx: ChatwootFlowContext):
    ctx.message_history = await get_last_ten_messages(ctx.tenant_settings, ctx.payload)


async def classify_current_message(ctx: ChatwootFlowContext):
    ctx.classification = await classify_chatwoot_message(
        ctx.message_history,
        ctx.current_message,
    )
    ctx.category = get_classification_category(ctx.classification)
    ctx.handoff_reason = get_classification_data(ctx.classification).get("reason")


async def build_bot_response(ctx: ChatwootFlowContext):
    if ctx.category == "CHITCHAT":
        ctx.response = await respond_to_chitchat(ctx.current_message)
        return

    if ctx.category == "RETRIEVAL":
        await build_rag_response(ctx)
        return

    if ctx.category == "OUT_OF_SCOPE":
        ctx.handoff_reason = (
            ctx.handoff_reason
            or "Request is outside basic approved business answers."
        )

    await build_handoff_response(ctx)


async def build_rag_response(ctx: ChatwootFlowContext):
    response = await respond_with_rag(ctx.tenant_settings, ctx.current_message)

    if isinstance(response, dict) and response.get("handoff_required") is True:
        ctx.category = "HANDOFF"
        ctx.handoff_required = True
        ctx.handoff_reason = response.get("reason")
        await build_handoff_response(ctx)
        return

    ctx.response = response


async def build_handoff_response(ctx: ChatwootFlowContext):
    ctx.category = "HANDOFF"
    ctx.handoff_required = True
    ctx.response = await respond_to_handoff(
        ctx.message_history,
        ctx.current_message,
        handoff_reason=ctx.handoff_reason,
    )


async def send_bot_response(ctx: ChatwootFlowContext):
    if not ctx.response:
        return

    sent_message = await send_message_to_chatwoot(
        ctx.tenant_settings,
        ctx.payload,
        ctx.response,
    )
    ctx.response_sent = sent_message is not None


async def run_handoff_flow_if_needed(ctx: ChatwootFlowContext):
    if not ctx.handoff_required:
        return

    await open_chatwoot_conversation(ctx)
    await sync_crm_contact_after_handoff(ctx)
    await add_crm_handoff_summary(ctx)


async def open_chatwoot_conversation(ctx: ChatwootFlowContext):
    await update_conversation_status_to_open(ctx.tenant_settings, ctx.payload)


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
    ctx: ChatwootFlowContext,
    reason: str,
):
    if not ctx.tenant_settings:
        return

    try:
        await open_chatwoot_conversation(ctx)
        logger.info(
            "Opened Chatwoot conversation for tenant slug '%s' after bot %s",
            ctx.slug,
            reason,
        )
    except Exception:
        logger.exception(
            "Failed to open Chatwoot conversation for tenant slug '%s' after bot %s",
            ctx.slug,
            reason,
        )


async def increment_subscription_usage_if_needed(ctx: ChatwootFlowContext):
    if not ctx.should_count_usage or not ctx.tenant_settings:
        return

    try:
        await svc_increment_subscription_usage(ctx.tenant_settings.tenant.id)
    except Exception:
        logger.exception(
            "Failed to increment subscription usage for tenant slug '%s'",
            ctx.slug,
        )


async def sync_crm_contact_after_handoff(ctx: ChatwootFlowContext):
    try:
        await sync_chatwoot_contact_payload_to_crm(ctx.slug, ctx.payload)
    except Exception:
        logger.exception(
            "Failed to create or update CRM contact during Chatwoot handoff for tenant slug '%s'",
            ctx.slug,
        )


async def add_crm_handoff_summary(ctx: ChatwootFlowContext):
    try:
        summary = await summarize_chatwoot_messages(ctx.message_history)
        if not summary:
            return

        crm_handler = get_conversation_summary_crm_handler(ctx.tenant_settings)
        crm_target = await crm_handler.resolve_summary_target(ctx.payload)
        await crm_handler.send_summary(crm_target, summary)
    except Exception:
        logger.exception("Failed to add Chatwoot handoff summary to CRM")


def log_chatwoot_webhook_failure(ctx: ChatwootFlowContext):
    logger.exception("Failed to process Chatwoot webhook for tenant slug '%s'", ctx.slug)
