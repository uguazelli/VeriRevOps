import logging
import json
import httpx
from fastapi import HTTPException
from src.services.image_analysis import analyze_image as analyze_image_file
from src.services.media_downloader import download_file_from_url
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

        # 3 - If audio message, transcribe it
        if message_kind == "audio":
            await transcribe_audio(payload)

        # 4 - If image message, describe it
        if message_kind == "image":
            await analyze_image(payload)

        # 5 - Get message history from Chatwoot API
        await get_last_ten_messages(_tenant_settings)

        # 5 - Classify if it requires RAG, handle to a human or if is just a small talk
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


async def get_last_ten_messages(tenant_settings):
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

    base_url = chatwoot_service.url.rstrip("/")
    messages_url = (
        f"{base_url}/api/v1/accounts/{chatwoot_service.account_id}/"
        "conversations/1/messages?after=1"
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
