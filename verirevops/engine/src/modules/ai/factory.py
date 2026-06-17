import logging
import os
from typing import Any

from llama_index.llms.google_genai import GoogleGenAI
from llama_index.llms.openai import OpenAI

logger = logging.getLogger(__name__)

_llm_instances = {}
_openai_async_client = None
_genai_client = None


def normalize_gemini_model_name(model_name: str | None = None) -> str:
    model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    if not model_name.startswith("models/"):
        return f"models/{model_name}"
    return model_name


class _GeminiModelAdapter:
    """Adapts the new google-genai Client to the old GenerativeModel.generate_content() interface."""

    def __init__(self, client: Any, model_name: str) -> None:
        self._client = client
        self._model_name = model_name

    def generate_content(self, contents: list) -> Any:
        from google.genai import types as _types

        converted = []
        for item in contents:
            if isinstance(item, dict) and "mime_type" in item and "data" in item:
                converted.append(_types.Part.from_bytes(data=item["data"], mime_type=item["mime_type"]))
            else:
                converted.append(item)  # str or PIL Image — passed through directly

        return self._client.models.generate_content(model=self._model_name, contents=converted)


def get_text_llm(provider: str = "gemini") -> Any:
    """Return a cached LLM instance for the requested provider."""
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
    """Return a cached async OpenAI client."""
    global _openai_async_client

    if _openai_async_client is not None:
        return _openai_async_client

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    from openai import AsyncOpenAI
    _openai_async_client = AsyncOpenAI(api_key=api_key)
    return _openai_async_client


def get_genai_client() -> Any:
    """Return a cached google.genai Client (new SDK)."""
    global _genai_client

    if _genai_client is None:
        from google import genai
        _genai_client = genai.Client(api_key=_get_google_api_key())

    return _genai_client


def get_gemini_model(model_name: str | None = None) -> _GeminiModelAdapter:
    """Return an adapter that exposes generate_content() using the new google-genai SDK."""
    return _GeminiModelAdapter(get_genai_client(), normalize_gemini_model_name(model_name))


def build_fresh_text_llm(provider: str = "gemini") -> Any:
    """Build a new uncached LLM instance, safe for use inside threads."""
    if provider == "openai":
        return _build_openai_llm()
    return _build_gemini_llm()


def _build_openai_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not found. Falling back to Gemini.")
        return get_text_llm("gemini")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    return OpenAI(model=model_name, api_key=api_key)


def _build_gemini_llm():
    return GoogleGenAI(
        model=normalize_gemini_model_name(),
        api_key=_get_google_api_key(),
    )


def _get_google_api_key() -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set.")
    return api_key
