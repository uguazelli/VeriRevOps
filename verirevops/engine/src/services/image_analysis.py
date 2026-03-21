import os
import io
import logging
import base64
from typing import Optional
import google.generativeai as genai
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

async def analyze_image_openai(file_bytes: bytes, mime_type: str, prompt: str) -> str:
    """
    Analyze image using OpenAI GPT-4o.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    client = AsyncOpenAI(api_key=api_key)

    # Encode image to base64
    base64_image = base64.b64encode(file_bytes).decode('utf-8')
    image_url = f"data:{mime_type};base64,{base64_image}"

    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI Image Analysis failed: {e}")
        raise e

async def analyze_image_gemini(file_bytes: bytes, mime_type: str, prompt: str) -> str:
    """
    Analyze image using Google Gemini (GenAI).
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    genai.configure(api_key=api_key)

    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"
    model = genai.GenerativeModel(model_name)

    try:
        response = model.generate_content([
            prompt,
            {
                "mime_type": mime_type,
                "data": file_bytes
            }
        ])
        return response.text
    except Exception as e:
        logger.error(f"Gemini Image Analysis failed: {e}")
        raise e

async def analyze_image(file_bytes: bytes, filename: str, prompt: str, provider: str = "gemini") -> str:
    """
    Router for image analysis.
    """
    # Simple mime type guess
    mime_type = "image/jpeg"
    lower_name = filename.lower()
    if lower_name.endswith(".png"):
        mime_type = "image/png"
    elif lower_name.endswith(".webp"):
        mime_type = "image/webp"
    elif lower_name.endswith(".gif"):
        mime_type = "image/gif"

    if provider.lower() == "openai":
        return await analyze_image_openai(file_bytes, mime_type, prompt)
    else:
        # Default to Gemini
        return await analyze_image_gemini(file_bytes, mime_type, prompt)
