import io
import logging
import os

import google.generativeai as genai
from openai import AsyncOpenAI

from src.modules.ai.factory import normalize_gemini_model_name


logger = logging.getLogger(__name__)


async def transcribe_openai(file_bytes: bytes, filename: str = "audio.mp3") -> str:
    """
    Transcribe audio using OpenAI Whisper.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    client = AsyncOpenAI(api_key=api_key)

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
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(normalize_gemini_model_name())

    try:
        response = model.generate_content([
            "Transcribe this audio file exactly as spoken.",
            {
                "mime_type": mime_type,
                "data": file_bytes,
            },
        ])
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
