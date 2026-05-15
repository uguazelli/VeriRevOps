"""
Compatibility wrapper for RAG reranking.

New code should import from src.modules.rag.reranking.
"""

from src.modules.rag.reranking import rerank_documents

__all__ = [
    "rerank_documents",
]

