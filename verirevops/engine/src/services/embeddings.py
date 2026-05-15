"""
Compatibility wrapper for RAG embeddings.

New code should import from src.modules.rag.embeddings.
"""

from src.modules.rag.embeddings import CustomGeminiEmbedding, get_embed_model

__all__ = [
    "CustomGeminiEmbedding",
    "get_embed_model",
]

