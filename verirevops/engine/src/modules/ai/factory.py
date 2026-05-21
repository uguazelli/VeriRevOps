import logging
import os
from typing import Any

from llama_index.llms.gemini import Gemini
from llama_index.llms.openai import OpenAI

logger = logging.getLogger(__name__)

_llm_instances = {}
_openai_async_client = None
_gemini_model_instances = {}


def normalize_gemini_model_name(model_name: str | None = None) -> str:
    model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    if not model_name.startswith("models/"):
        return f"models/{model_name}"

    return model_name


def get_text_llm(provider: str = "gemini") -> Any:
    """
    Return a cached LLM instance for the requested provider.
    """
    provider = provider.lower()

    if provider in _llm_instances:
        return _llm_instances[provider]

    logger.info("Initializing LLM provider: %s", provider)

    if provider == "openai":
        llm = _build_openai_llm()
    elif provider == "gemini":
        llm = _build_gemini_llm()
    else:
        logger.warning("Unknown provider '%s'. Defaulting to Gemini.", provider)
        return get_text_llm("gemini")

    _llm_instances[provider] = llm
    return llm


def get_openai_async_client() -> Any:
    """
    Return a cached async OpenAI client for provider APIs outside LlamaIndex.
    """
    global _openai_async_client

    if _openai_async_client is not None:
        return _openai_async_client

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    from openai import AsyncOpenAI

    _openai_async_client = AsyncOpenAI(api_key=api_key)
    return _openai_async_client


def get_gemini_model(model_name: str | None = None) -> Any:
    """
    Return a cached Google Generative AI model for multimodal provider calls.
    """
    model_name = normalize_gemini_model_name(model_name)

    if model_name in _gemini_model_instances:
        return _gemini_model_instances[model_name]

    api_key = _get_google_api_key()

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    _gemini_model_instances[model_name] = model
    return model


def _build_openai_llm():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        logger.error("OPENAI_API_KEY not found. Falling back to Gemini.")
        return get_text_llm("gemini")

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    return OpenAI(model=model_name, api_key=api_key)


def _build_gemini_llm():
    return Gemini(
        model=normalize_gemini_model_name(),
        api_key=_get_google_api_key(),
    )


def _get_google_api_key() -> str:
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set.")

    return api_key
