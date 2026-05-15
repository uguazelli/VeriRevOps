import base64
import io
import logging
import os

import google.generativeai as genai
from llama_index.multi_modal_llms.gemini import GeminiMultiModal
from openai import AsyncOpenAI
from PIL import Image

from src.core.prompts import VLM_IMAGE_DESCRIPTION_PROMPT
from src.modules.ai.factory import normalize_gemini_model_name


logger = logging.getLogger(__name__)

_vlm = None


def get_vlm():
    """
    Return a cached Gemini multi-modal model.
    """
    global _vlm

    if _vlm is None:
        _vlm = GeminiMultiModal(
            model_name=normalize_gemini_model_name(),
            api_key=os.getenv("GOOGLE_API_KEY"),
        )

    return _vlm


def describe_image(image_bytes: bytes, filename: str) -> str:
    """
    Generate a detailed text description of an image using Gemini.
    """
    try:
        logger.info("Generating caption for image: %s", filename)

        api_key = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(normalize_gemini_model_name())
        image = Image.open(io.BytesIO(image_bytes))

        response = model.generate_content([VLM_IMAGE_DESCRIPTION_PROMPT, image])
        description = response.text

        logger.info("Caption generated: %s...", description[:100])
        return description
    except Exception as exc:
        logger.error("VLM generation failed: %s", exc)
        return f"Image: {filename} (Description failed)"


async def analyze_image_openai(file_bytes: bytes, mime_type: str, prompt: str) -> str:
    """
    Analyze an image using OpenAI.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    client = AsyncOpenAI(api_key=api_key)
    base64_image = base64.b64encode(file_bytes).decode("utf-8")
    image_url = f"data:{mime_type};base64,{base64_image}"

    try:
        response = await client.chat.completions.create(
            model=os.getenv("OPENAI_VISION_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o")),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                    ],
                }
            ],
            max_tokens=1000,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("OpenAI image analysis failed: %s", exc)
        raise


async def analyze_image_gemini(file_bytes: bytes, mime_type: str, prompt: str) -> str:
    """
    Analyze an image using Gemini.
    """
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(normalize_gemini_model_name())

    try:
        response = model.generate_content([
            prompt,
            {
                "mime_type": mime_type,
                "data": file_bytes,
            },
        ])
        return response.text
    except Exception as exc:
        logger.error("Gemini image analysis failed: %s", exc)
        raise


async def analyze_image(
    file_bytes: bytes,
    filename: str,
    prompt: str,
    provider: str = "gemini",
) -> str:
    """
    Route image analysis to the requested provider.
    """
    mime_type = get_image_mime_type(filename)

    if provider.lower() == "openai":
        return await analyze_image_openai(file_bytes, mime_type, prompt)

    return await analyze_image_gemini(file_bytes, mime_type, prompt)


def get_image_mime_type(filename: str) -> str:
    lower_name = filename.lower()

    if lower_name.endswith(".png"):
        return "image/png"

    if lower_name.endswith(".webp"):
        return "image/webp"

    if lower_name.endswith(".gif"):
        return "image/gif"

    return "image/jpeg"
