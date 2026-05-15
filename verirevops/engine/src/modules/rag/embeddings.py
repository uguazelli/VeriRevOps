import logging
import os
from typing import Any, List, Optional

import google.generativeai as genai
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.embeddings import BaseEmbedding


logger = logging.getLogger(__name__)

_embed_model = None


class CustomGeminiEmbedding(BaseEmbedding):
    """
    Custom wrapper for Google Gemini Embeddings using the official library directly.
    """
    _model_name: str = PrivateAttr()
    _api_key: str = PrivateAttr()

    def __init__(
        self,
        model_name: str = "models/gemini-embedding-001",
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._model_name = model_name
        self._api_key = api_key
        if api_key:
            genai.configure(api_key=api_key)

    def _get_query_embedding(self, query: str) -> List[float]:
        return self._get_embedding(query)

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._get_embedding(text)

    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self._get_embedding(text) for text in texts]

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return self._get_query_embedding(query)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return self._get_text_embedding(text)

    def _get_embedding(self, text: str) -> List[float]:
        result = genai.embed_content(
            model=self._model_name,
            content=text,
            task_type="retrieval_document",
        )
        return result["embedding"]


def get_embed_model():
    """
    Factory to get the Gemini embedding model.
    """
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

