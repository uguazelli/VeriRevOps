import logging
import json
import httpx
from fastapi import HTTPException
from src.core.prompts import CHATWOOT_TRAFFIC_CLASSIFIER_PROMPT
from src.services.image_analysis import analyze_image as analyze_image_file
from src.services.media_downloader import download_file_from_url
from src.services.chat_messages import svc_list_chat_messages
from src.services.llm import get_chat_response
from src.services.tenants import svc_get_tenant_by_slug
from src.services.transcription import transcribe_audio as transcribe_audio_file


logger = logging.getLogger(__name__)


async def process_chatwoot_webhook(slug: str, payload: dict):
    try:
        should_respond = process_chatwoot_payload(payload)
        if not should_respond["shouldBotRespond"]:
            return

        message_kind = get_message_kind(payload)

        # 2 - Get tenant settings
        _tenant_settings = await svc_get_tenant_by_slug(slug)

        current_message = get_text_message_content(payload)

        # 3 - If audio message, transcribe it
        if message_kind == "audio":
            current_message = await transcribe_audio(payload)

        # 4 - If image message, describe it
        if message_kind == "image":
            current_message = await analyze_image(payload)

        # 5 - Get message history from Chatwoot API
        message_history = await get_last_ten_messages(_tenant_settings, payload)

        # 6 - Classify if it requires RAG, handle to a human or if is just a small talk
        await classify_chatwoot_message(message_history, current_message)

        # 6 - If small talk, generate answer with LLM and send to Chatwoot API
        # 7 - If Handle to human, send message to Chatwoot API and update status to open
        # 8 - If RAG, generate answer with retrieved context and send to Chatwoot API
    except Exception:
        log_chatwoot_webhook_failure(slug)


def log_chatwoot_webhook_failure(slug: str):
    logger.exception("Failed to process Chatwoot webhook for tenant slug '%s'", slug)


def process_chatwoot_payload(item):
    body = item.get("body", item)

    status = body.get("conversation", {}).get("status")
    message_type = body.get("message_type")
    is_private = body.get("private")
    event = body.get("event")

    should_respond = (
        status != "open"
        and message_type == "incoming"
        and is_private is False
        and event == "message_created"
    )

    reason = None

    if status == "open":
        reason = "status open"
    elif message_type != "incoming":
        reason = f"message_type {message_type}"
    elif is_private is not False:
        reason = "private message"
    elif event != "message_created":
        reason = f"event {event}"

    result = {
        "shouldBotRespond": should_respond,
        "reason": reason
    }

    logger.info("Processed Chatwoot payload: %s", result)
    if not should_respond:
        logger.info("Skipping Chatwoot response: %s", reason)

    return result


def get_message_contents(messages):
    if not isinstance(messages, list):
        return []

    return [
        message.get("content")
        for message in messages
        if isinstance(message, dict) and message.get("content")
    ]


def get_text_message_content(payload):
    body = payload.get("body", payload)
    content = body.get("content")

    if isinstance(content, str) and content.strip():
        return content.strip()

    return ""


def get_chatwoot_conversation_id(payload):
    body = payload.get("body", payload)
    conversation = body.get("conversation") or {}
    conversation_id = conversation.get("id") or body.get("conversation_id")

    if not conversation_id:
        raise HTTPException(
            status_code=400,
            detail="Chatwoot payload is missing conversation id"
        )

    return int(conversation_id)


def get_last_tracked_message_id(chat_messages):
    if not chat_messages:
        return 0

    latest_message = max(
        chat_messages,
        key=lambda message: message.id or 0
    )
    return latest_message.message_id


def normalize_chatwoot_history(messages):
    if not isinstance(messages, list):
        return []

    normalized_messages = []

    for message in messages:
        if not isinstance(message, dict):
            continue

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        message_type = message.get("message_type")
        role = "assistant" if message_type == 1 else "user"
        normalized_messages.append({
            "role": role,
            "content": content.strip()
        })

    return normalized_messages


def build_chatwoot_classification_prompt(message_history, current_message):
    normalized_history = normalize_chatwoot_history(message_history)
    history_json = json.dumps(normalized_history, indent=2, default=str)
    current_message_text = current_message.strip() if current_message else "EMPTY_QUERY"

    return CHATWOOT_TRAFFIC_CLASSIFIER_PROMPT.format(
        message_history=history_json,
        current_message=current_message_text
    )


def parse_chatwoot_classification(raw_response):
    response_text = raw_response.strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}")

    if start != -1 and end != -1 and start < end:
        try:
            return json.loads(response_text[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse Chatwoot classification JSON: %s", raw_response)
    return {
        "data": {
            "category": "HANDOFF",
            "confidence": 0.0,
            "reason": "classifier returned invalid JSON"
        }
    }


async def classify_chatwoot_message(message_history, current_message, provider: str = "gemini"):
    prompt = build_chatwoot_classification_prompt(message_history, current_message)
    raw_response = await get_chat_response(prompt, provider=provider)
    classification = parse_chatwoot_classification(raw_response)
    logger.info("☎️ Chatwoot message classification: %s", classification)
    return classification


def get_message_kind(item):
    body = item.get("body", item)

    attachments = body.get("attachments") or []

    if attachments:
        message_kind = attachments[0].get("file_type", "unknown")
    else:
        message_kind = "text"

    logger.info("Chatwoot message kind: %s", message_kind)
    return message_kind


def get_first_attachment_url(item):
    body = item.get("body", item)
    attachments = body.get("attachments") or []

    if not attachments:
        return None

    attachment = attachments[0]
    for key in ("data_url", "download_url", "url", "file_url", "attachment_url"):
        url = attachment.get(key)
        if url:
            return url

    return None


async def transcribe_audio(payload, provider: str = "gemini"):
    logger.info("Transcribing Chatwoot audio message ...")
    audio_url = get_first_attachment_url(payload)

    if not audio_url:
        raise HTTPException(
            status_code=400,
            detail="Audio message has no downloadable attachment URL"
        )

    audio_bytes, filename = await download_file_from_url(audio_url)
    transcription = await transcribe_audio_file(audio_bytes, filename, provider)
    logger.info("Transcription result: %s", transcription)
    return transcription


async def analyze_image(
    payload,
    prompt: str = "Describe this image in detail.",
    provider: str = "gemini"
):
    logger.info("Describing Chatwoot image message ...")
    image_url = get_first_attachment_url(payload)

    if not image_url:
        raise HTTPException(
            status_code=400,
            detail="Image message has no downloadable attachment URL"
        )

    image_bytes, filename = await download_file_from_url(image_url)
    image_description = await analyze_image_file(image_bytes, filename, prompt, provider)
    logger.info("Image description: %s", image_description)
    return image_description


async def get_last_ten_messages(tenant_settings, payload):
    chatwoot_service = tenant_settings.tenant.services.get("chatwoot")

    if not chatwoot_service:
        raise HTTPException(
            status_code=400,
            detail="Tenant has no chatwoot service configured"
        )

    if not chatwoot_service.url or not chatwoot_service.api_key or not chatwoot_service.account_id:
        raise HTTPException(
            status_code=400,
            detail="Chatwoot service is missing url, api_key, or account_id"
        )

    tenant_id = tenant_settings.tenant.id
    chatwoot_account_id = int(chatwoot_service.account_id)
    chatwoot_conversation_id = get_chatwoot_conversation_id(payload)
    tracked_messages = await svc_list_chat_messages(
        tenant_id,
        chatwoot_account_id,
        chatwoot_conversation_id
    )
    after_message_id = get_last_tracked_message_id(tracked_messages)

    base_url = chatwoot_service.url.rstrip("/")
    messages_url = (
        f"{base_url}/api/v1/accounts/{chatwoot_service.account_id}/"
        f"conversations/{chatwoot_conversation_id}/messages?after={after_message_id}"
    )
    logger.info(
        "Fetching Chatwoot messages for account=%s conversation=%s after=%s",
        chatwoot_account_id,
        chatwoot_conversation_id,
        after_message_id
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            messages_url,
            headers={"api_access_token": chatwoot_service.api_key},
            timeout=30.0
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.exception("Failed to fetch Chatwoot messages")
        raise HTTPException(
            status_code=exc.response.status_code,
            detail="Failed to fetch Chatwoot messages"
        ) from exc

    data = response.json()
    messages = data.get("payload", data)

    if isinstance(messages, list):
        last_messages = messages[-10:]
        logger.info("Fetched %s Chatwoot messages", len(last_messages))
        logger.info(
            "Fetched Chatwoot message contents: %s",
            json.dumps(get_message_contents(last_messages), indent=2, default=str)
        )
        return last_messages

    logger.info("Fetched Chatwoot messages response with unexpected shape")
    return messages
