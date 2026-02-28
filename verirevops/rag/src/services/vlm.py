import os
import logging
from llama_index.multi_modal_llms.gemini import GeminiMultiModal
from llama_index.core.multi_modal_llms.generic_utils import load_image_urls
from llama_index.core.schema import ImageDocument

logger = logging.getLogger(__name__)

_vlm = None

def get_vlm():
    """
    Factory to get the Gemini Multi-Modal model.
    """
    global _vlm
    if _vlm is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        model_name = os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash")
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        _vlm = GeminiMultiModal(model_name=model_name, api_key=api_key)
    return _vlm

def describe_image(image_bytes: bytes, filename: str) -> str:
    """
    Generates a detailed text description of an image using Gemini.
    """
    try:
        logger.info(f"Generating caption for image: {filename}")

        import google.generativeai as genai
        from PIL import Image
        import io

        api_key = os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)

        model_name = os.getenv("GEMINI_MODEL", "models/gemini-2.0-flash")
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"

        model = genai.GenerativeModel(model_name)

        image = Image.open(io.BytesIO(image_bytes))

        prompt = (
            "Describe this image in extreme detail for retrieval purposes. "
            "Include any visible text, numbers, layout structure, and visual elements. "
            "The goal is to allow someone to find this image by searching for its content."
        )

        response = model.generate_content([prompt, image])
        description = response.text

        logger.info(f"Caption generated: {description[:100]}...")
        return description

    except Exception as e:
        logger.error(f"VLM generation failed: {e}")
        return f"Image: {filename} (Description failed)"
