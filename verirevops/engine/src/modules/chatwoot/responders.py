import json
import logging

from fastapi import HTTPException

from src.core.prompts import CHATWOOT_CHITCHAT_PROMPT, CHATWOOT_HANDOFF_PROMPT
from src.modules.chatwoot.payload import get_first_attachment_url, normalize_chatwoot_history
from src.services.image_analysis import analyze_image as analyze_image_file
from src.services.llm import get_chat_response
from src.services.media_downloader import download_file_from_url
from src.services.rag import generate_answer
from src.services.transcription import transcribe_audio as transcribe_audio_file


logger = logging.getLogger(__name__)


def build_chitchat_prompt(current_message):
    current_message_text = current_message.strip() if current_message else "EMPTY_QUERY"
    return CHATWOOT_CHITCHAT_PROMPT.format(current_message=current_message_text)


def parse_chitchat_response(raw_response):
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

    logger.error("Failed to parse Chatwoot chitchat JSON: %s", raw_response)
    return {
        "data": raw_response.strip()
    }


async def respond_to_chitchat(current_message, provider: str = "gemini"):
    prompt = build_chitchat_prompt(current_message)
    raw_response = await get_chat_response(prompt, provider=provider)
    response = parse_chitchat_response(raw_response)
    logger.info("Chatwoot chitchat response: %s", response)
    return response


def build_handoff_prompt(message_history, current_message):
    normalized_history = normalize_chatwoot_history(message_history)
    history_json = json.dumps(normalized_history, indent=2, default=str)
    current_message_text = current_message.strip() if current_message else "EMPTY_QUERY"

    return CHATWOOT_HANDOFF_PROMPT.format(
        message_history=history_json,
        current_message=current_message_text
    )


def parse_handoff_response(raw_response):
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

    logger.error("Failed to parse Chatwoot handoff JSON: %s", raw_response)
    return {
        "data": raw_response.strip()
    }


async def respond_to_handoff(message_history, current_message, provider: str = "gemini"):
    prompt = build_handoff_prompt(message_history, current_message)
    raw_response = await get_chat_response(prompt, provider=provider)
    response = parse_handoff_response(raw_response)
    logger.info("Chatwoot handoff response: %s", response)
    return response


async def respond_with_rag(tenant_settings, current_message, provider: str = "gemini"):
    answer = await generate_answer(
        tenant_settings.tenant.id,
        current_message,
        provider=provider
    )
    logger.info("Chatwoot RAG response: %s", answer)
    return answer


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
