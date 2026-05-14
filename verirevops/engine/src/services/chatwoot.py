from fastapi import HTTPException
from src.services.image_analysis import analyze_image as analyze_image_file
from src.services.media_downloader import download_file_from_url
from src.services.transcription import transcribe_audio as transcribe_audio_file


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
