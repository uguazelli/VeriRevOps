import logging

from src.modules.chatwoot.classifier import classify_chatwoot_message, get_classification_category
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
from src.modules.chatwoot.responders import (
    analyze_image,
    respond_to_chitchat,
    respond_to_handoff,
    respond_to_out_of_scope,
    respond_with_rag,
    transcribe_audio,
)
from src.modules.tenants import svc_get_tenant_by_slug


logger = logging.getLogger(__name__)


async def process_chatwoot_webhook(slug: str, payload: dict):
    try:
        # 1 - Process and validate Chatwoot payload to decide if it requires a response
        should_respond = process_chatwoot_payload(payload)
        if not should_respond["shouldBotRespond"]:
            return

        # 2 - Determine message kind (text, audio, image, etc)
        message_kind = get_message_kind(payload)

        # 3 - Get tenant settings
        _tenant_settings = await svc_get_tenant_by_slug(slug)

        current_message = get_text_message_content(payload)

        # 4 - If audio message, transcribe it
        if message_kind == "audio":
            current_message = await transcribe_audio(payload)

        # 5 - If image message, describe it
        if message_kind == "image":
            current_message = await analyze_image(payload)

        # 6 - Get message history from Chatwoot API
        message_history = await get_last_ten_messages(_tenant_settings, payload)

        # 7 - Classify if it requires RAG, handle to a human or if is just a small talk
        classification = await classify_chatwoot_message(message_history, current_message)
        category = get_classification_category(classification)
        response = None

        # 8 - If small talk, generate answer with LLM and send to Chatwoot API
        if category == "CHITCHAT":
            response = await respond_to_chitchat(current_message)

        # 9 - If Handle to human, send message to Chatwoot API and update status to open
        if category == "HANDOFF":
            response = await respond_to_handoff(message_history, current_message)

        # 10 - If out of scope, generate a refusal in the client's language
        if category == "OUT_OF_SCOPE":
            response = await respond_to_out_of_scope(current_message)

        # 11 - If RAG, generate answer with retrieved context and send to Chatwoot API
        if category == "RETRIEVAL":
            response = await respond_with_rag(_tenant_settings, current_message)

        # 12 - Send response back to Chatwoot API
        if response:
            await send_message_to_chatwoot(_tenant_settings, payload, response)

        # 13 - If handoff, update conversation status to open
        if category == "HANDOFF":
            await update_conversation_status_to_open(_tenant_settings, payload)

    except Exception:
        log_chatwoot_webhook_failure(slug)


def log_chatwoot_webhook_failure(slug: str):
    logger.exception("Failed to process Chatwoot webhook for tenant slug '%s'", slug)
