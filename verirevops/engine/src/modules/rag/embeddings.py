import logging
import os
from typing import Any

from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.embeddings import BaseEmbedding


logger = logging.getLogger(__name__)

_embed_model = None


class CustomGeminiEmbedding(BaseEmbedding):
    """Wrapper for Google Gemini Embeddings using the google-genai SDK."""

    _model_name: str = PrivateAttr()
    _api_key: str = PrivateAttr()
    _client: Any = PrivateAttr(default=None)

    def __init__(
        self,
        model_name: str = "models/gemini-embedding-001",
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._model_name = model_name
        self._api_key = api_key or ""
        from google import genai
        self._client = genai.Client(api_key=self._api_key)

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._get_embedding(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._get_embedding(text)

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return [self._get_embedding(text) for text in texts]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._get_text_embedding(text)

    def _get_embedding(self, text: str) -> list[float]:
        from google.genai import types as _types
        result = self._client.models.embed_content(
            model=self._model_name,
            contents=text,
            config=_types.EmbedContentConfig(task_type="retrieval_document"),
        )
        return result.embeddings[0].values


def get_embed_model():
    """Factory to get the cached Gemini embedding model."""
    global _embed_model
    if _embed_model is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY not set.")
        logger.info("Using Google Gemini Embeddings (models/gemini-embedding-001)")
        _embed_model = CustomGeminiEmbedding(
            model_name="models/gemini-embedding-001",
            api_key=api_key,
        )
    return _embed_model
