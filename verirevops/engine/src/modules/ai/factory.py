import logging
import os
from typing import Any

from llama_index.llms.gemini import Gemini
from llama_index.llms.openai import OpenAI


logger = logging.getLogger(__name__)

_llm_instances = {}


def normalize_gemini_model_name(model_name: str | None = None) -> str:
    model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    if not model_name.startswith("models/"):
        return f"models/{model_name}"

    return model_name


def get_llm(provider: str = "gemini") -> Any:
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
        return get_llm("gemini")

    _llm_instances[provider] = llm
    return llm


def get_hyde_llm(provider: str = "gemini") -> Any:
    return get_llm(provider)


def get_rerank_llm(provider: str = "gemini") -> Any:
    return get_llm(provider)


def _build_openai_llm():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        logger.error("OPENAI_API_KEY not found. Falling back to Gemini.")
        return get_llm("gemini")

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    return OpenAI(model=model_name, api_key=api_key)


def _build_gemini_llm():
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set.")

    return Gemini(
        model=normalize_gemini_model_name(),
        api_key=api_key,
    )
