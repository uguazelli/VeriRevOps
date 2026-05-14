import logging

import httpx
from fastapi import HTTPException

from src.services.image_analysis import analyze_image as analyze_image_file
from src.services.media_downloader import download_file_from_url
from src.services.tenants import svc_get_tenant_by_slug
from src.services.transcription import transcribe_audio as transcribe_audio_file


logger = logging.getLogger(__name__)

CHATWOOT_MESSAGES_URL = (
    "https://dev-chat.veridatapro.com//api/v1/accounts/1/"
    "conversations/1/messages?after=1"
)
CHATWOOT_API_ACCESS_TOKEN = "DYdAi4Wf9jVXcXRux2Pe5UHJ"


async def process_chatwoot_webhook(slug: str, payload: dict):
    try:
        should_respond = process_chatwoot_payload(payload)
        logger.info("Processed Chatwoot payload: %s", should_respond)

        if not should_respond["shouldBotRespond"]:
            logger.info("Skipping Chatwoot response: %s", should_respond["reason"])
            return

        message_kind = get_message_kind(payload)
        logger.info("Chatwoot message kind: %s", message_kind)

        # 2 - Get tenant settings
        _tenant_settings = await svc_get_tenant_by_slug(slug)

        # 3 - If audio message, transcribe it
        transcription = None
        if message_kind == "audio":
            logger.info("Transcribing Chatwoot audio message ...")
            transcription = await transcribe_audio(payload)
            logger.info("Transcription result: %s", transcription)

        # 4 - If image message, describe it
        image_description = None
        if message_kind == "image":
            logger.info("Describing Chatwoot image message ...")
            image_description = await analyze_image(payload)
            logger.info("Image description: %s", image_description)

        # 5 - Get message history from Chatwoot API
        message_history = await get_last_ten_messages()
        logger.info(
            "Fetched %s Chatwoot messages",
            len(message_history) if isinstance(message_history, list) else "unknown"
        )

        # 5 - Classify if it requires RAG, handle to a human or if is just a small talk
        # 6 - If small talk, generate answer with LLM and send to Chatwoot API
        # 7 - If Handle to human, send message to Chatwoot API and update status to open
        # 8 - If RAG, generate answer with retrieved context and send to Chatwoot API
    except Exception:
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

    return {
        "shouldBotRespond": should_respond,
        "reason": reason
    }


def get_message_kind(item):
    body = item.get("body", item)

    attachments = body.get("attachments") or []

    if attachments:
        return attachments[0].get("file_type", "unknown")

    return "text"


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
    audio_url = get_first_attachment_url(payload)

    if not audio_url:
        raise HTTPException(
            status_code=400,
            detail="Audio message has no downloadable attachment URL"
        )

    audio_bytes, filename = await download_file_from_url(audio_url)
    return await transcribe_audio_file(audio_bytes, filename, provider)


async def analyze_image(
    payload,
    prompt: str = "Describe this image in detail.",
    provider: str = "gemini"
):
    image_url = get_first_attachment_url(payload)

    if not image_url:
        raise HTTPException(
            status_code=400,
            detail="Image message has no downloadable attachment URL"
        )

    image_bytes, filename = await download_file_from_url(image_url)
    return await analyze_image_file(image_bytes, filename, prompt, provider)


async def get_last_ten_messages():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            CHATWOOT_MESSAGES_URL,
            headers={"api_access_token": CHATWOOT_API_ACCESS_TOKEN},
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
        return messages[-10:]

    return messages
