"""RAG domain module."""

from src.modules.rag.ingestion import ingest_document
from src.modules.rag.retrieval import search_documents
from src.modules.rag.service import generate_answer

__all__ = [
    "generate_answer",
    "ingest_document",
    "search_documents",
]

