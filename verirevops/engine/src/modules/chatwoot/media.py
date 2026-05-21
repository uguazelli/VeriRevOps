import logging

from fastapi import HTTPException

from src.modules.ai.transcription import transcribe_audio as transcribe_audio_file
from src.modules.ai.vision import analyze_image as analyze_image_file
from src.modules.chatwoot.payload import get_first_attachment_url
from src.modules.media import download_file_from_url


logger = logging.getLogger(__name__)


async def transcribe_chatwoot_audio(payload, provider: str = "gemini"):
    logger.info("Transcribing Chatwoot audio message ...")
    audio_url = get_first_attachment_url(payload)

    if not audio_url:
        raise HTTPException(
            status_code=400,
            detail="Audio message has no downloadable attachment URL",
        )

    audio_bytes, filename = await download_file_from_url(audio_url)
    transcription = await transcribe_audio_file(audio_bytes, filename, provider)
    logger.info("Transcription result: %s", transcription)
    return transcription


async def analyze_chatwoot_image(
    payload,
    prompt: str = "Describe this image in detail.",
    provider: str = "gemini",
):
    logger.info("Describing Chatwoot image message ...")
    image_url = get_first_attachment_url(payload)

    if not image_url:
        raise HTTPException(
            status_code=400,
            detail="Image message has no downloadable attachment URL",
        )

    image_bytes, filename = await download_file_from_url(image_url)
    image_description = await analyze_image_file(image_bytes, filename, prompt, provider)
    logger.info("Image description: %s", image_description)
    return image_description
