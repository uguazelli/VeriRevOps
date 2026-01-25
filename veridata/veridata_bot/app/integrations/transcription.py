import logging
import os
from app.core.config import settings
from app.core.llm_config import get_llm_config

logger = logging.getLogger(__name__)


from google import genai
from google.genai import types


async def transcribe_gemini(file_bytes: bytes, mime_type: str = "audio/mp3") -> str:
    api_key = settings.google_api_key
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    client = genai.Client(api_key=api_key)

    config = await get_llm_config()
    model_name = config.get("model_name", "gemini-2.0-flash")
    if not model_name:
         model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_text(text="Transcribe this audio file exactly as spoken."),
                        types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                    ]
                )
            ],
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini Transcription failed: {e}")
        raise e


async def transcribe_audio(file_bytes: bytes, filename: str, provider: str = None) -> str:
    mime_type = "audio/mp3"
    if filename.endswith(".ogg"):
        mime_type = "audio/ogg"
    elif filename.endswith(".wav"):
        mime_type = "audio/wav"
    elif filename.endswith(".m4a"):
        mime_type = "audio/mp4"

    # Default and forced to Gemini
    return await transcribe_gemini(file_bytes, mime_type)
