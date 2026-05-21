import asyncio
import io
import logging

from src.modules.ai.factory import get_gemini_model, get_openai_async_client


logger = logging.getLogger(__name__)


async def transcribe_openai(file_bytes: bytes, filename: str = "audio.mp3") -> str:
    """
    Transcribe audio using OpenAI Whisper.
    """
    client = get_openai_async_client()

    file_obj = io.BytesIO(file_bytes)
    file_obj.name = filename

    try:
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=file_obj,
        )
        return transcript.text
    except Exception as exc:
        logger.error("OpenAI transcription failed: %s", exc)
        raise


async def transcribe_gemini(file_bytes: bytes, mime_type: str = "audio/mp3") -> str:
    """
    Transcribe audio using Google Gemini.
    """
    model = get_gemini_model()

    try:
        response = await asyncio.to_thread(
            model.generate_content,
            [
                "Transcribe this audio file exactly as spoken.",
                {
                    "mime_type": mime_type,
                    "data": file_bytes,
                },
            ],
        )
        return response.text
    except Exception as exc:
        logger.error("Gemini transcription failed: %s", exc)
        raise


async def transcribe_audio(file_bytes: bytes, filename: str, provider: str = "gemini") -> str:
    """
    Route transcription to the requested provider.
    """
    mime_type = get_audio_mime_type(filename)

    if provider.lower() == "openai":
        return await transcribe_openai(file_bytes, filename)

    return await transcribe_gemini(file_bytes, mime_type)


def get_audio_mime_type(filename: str) -> str:
    lower_name = filename.lower()

    if lower_name.endswith(".ogg"):
        return "audio/ogg"

    if lower_name.endswith(".wav"):
        return "audio/wav"

    if lower_name.endswith(".m4a"):
        return "audio/mp4"

    return "audio/mp3"
